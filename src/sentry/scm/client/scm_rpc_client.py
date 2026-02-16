from __future__ import annotations

import hashlib
import hmac
from enum import Enum
from typing import Any, TypedDict, overload

import orjson
import pydantic
import requests

from .types import (
    CheckRunActionResult,
    CheckRunOutput,
    CommentActionResult,
    CommitActionResult,
    CommitComparisonActionResult,
    FileContentActionResult,
    GitBlobActionResult,
    GitCommitObjectActionResult,
    GitRefActionResult,
    GitTreeActionResult,
    InputTreeEntry,
    PullRequestActionResult,
    PullRequestCommitActionResult,
    PullRequestDiffActionResult,
    PullRequestFileActionResult,
    Reaction,
    ReactionResult,
    RepositoryId,
    ReviewActionResult,
    ReviewCommentActionResult,
    ReviewCommentInput,
)

# Implementation details


def _generate_request_signature(shared_secret: str, url_path: str, body: bytes) -> str:
    signature_input = body
    signature = hmac.new(shared_secret.encode("utf-8"), signature_input, hashlib.sha256).hexdigest()
    return f"rpc0:{signature}"


class _CompositeRepositoryId(TypedDict):
    provider: str
    external_id: str


class _BasicArgs(TypedDict):
    organization_id: int
    repository_id: int | _CompositeRepositoryId


class _Error(pydantic.BaseModel):
    type: str
    details: list[Any]


class _Unset(Enum):
    """
    None is a valid value for field 'data', so we need a way to mark it as absent from the response.

    A single-valued Enum plays well with the type checker.
    """

    UNSET = "unset"


class _ResponseBody(pydantic.BaseModel):
    data: Any | _Unset = _Unset.UNSET
    errors: list[_Error] | _Unset = _Unset.UNSET


# Client interface


class SCMError(Exception):
    pass


class SCMProviderException(SCMError):
    pass


class SCMCodedError(SCMError):
    pass


class SCMUnhandledException(SCMError):
    pass


class SourceCodeManagerRPCClient:
    """
    base_url:
        E.g. "http://dev.getsentry.net:8000" (no trailing slash)

    shared_secret:
        The shared secret configured on the SCM RPC server side (SCM_RPC_SHARED_SECRET), used for authenticating requests

    organization_id:
        The Sentry organization ID that the SCM RPC requests will be made on behalf of

    repository_id:
        The repository ID that the SCM RPC requests will be made on.
        Either an internal integer repository ID, or (provider, external_id).

    session:
        You may pass in a `requests.Session` to the constructor if you want to manage the session lifecycle yourself
        (e.g. for connection pooling or custom configuration).
        If you do not pass in a session, the client will create its own session and manage its lifecycle internally.

        In both cases, you can call `.close()`. It will close the session if the client owns it,
        and do nothing if you passed in a session (since you manage its lifecycle).
        And in both cases, you can also use the client as a context manager, which will call `.close()` on exit.
    """

    # At the time of writing, the prefix is configured in:
    # - api/0: https://github.com/getsentry/sentry/blob/de54779095c3819213569ead2f28dfb6d0fe082e/src/sentry/web/urls.py#L178-L181
    # - internal: https://github.com/getsentry/sentry/blob/de54779095c3819213569ead2f28dfb6d0fe082e/src/sentry/api/urls.py#L3763-L3766
    # - scm-rpc: https://github.com/getsentry/sentry/blob/de54779095c3819213569ead2f28dfb6d0fe082e/src/sentry/api/urls.py#L3552-L3556
    API_PREFIX = "api/0/internal/scm-rpc"

    def __init__(
        self,
        *,
        base_url: str,
        shared_secret: str,
        organization_id: int,
        repository_id: RepositoryId,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url
        assert not self._base_url.endswith("/"), "base_url should not have a trailing slash"
        self._shared_secret = shared_secret

        if isinstance(repository_id, int):
            self._basic_args = _BasicArgs(
                organization_id=organization_id,
                repository_id=repository_id,
            )
        else:
            self._basic_args = _BasicArgs(
                organization_id=organization_id,
                repository_id=_CompositeRepositoryId(
                    provider=repository_id[0],
                    external_id=repository_id[1],
                ),
            )

        if session is None:
            self._session = requests.Session()
            self._owns_session = True
        else:
            self._session = session
            self._owns_session = False

    def __enter__(self) -> SourceCodeManagerRPCClient:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_session:
            self._session.close()

    @overload
    def _call[T](self, method: str, method_args: dict[str, Any], return_type: None) -> None: ...

    @overload
    def _call[T](self, method: str, method_args: dict[str, Any], return_type: type[T]) -> T: ...

    def _call[T](
        self, method: str, method_args: dict[str, Any], return_type: type[T] | None
    ) -> T | None:
        url = f"{self._base_url}/{self.API_PREFIX}/{method}/"
        body = orjson.dumps({"args": self._basic_args | method_args})
        signature = _generate_request_signature(self._shared_secret, url, body=body)
        headers = {
            "Authorization": f"rpcsignature {signature}",
            "Content-Type": "application/json",
        }

        response = self._session.post(url, data=body, headers=headers)

        try:
            response_json = response.json()
        except requests.exceptions.JSONDecodeError as e:
            raise SCMUnhandledException(
                "Response was not JSON", response.status_code, response.text
            ) from e

        try:
            response_body = _ResponseBody.parse_obj(response_json)
        except pydantic.ValidationError as e:
            raise SCMUnhandledException(
                "Response did not match expected schema", response.status_code, response_json
            ) from e

        if response_body.errors is not _Unset.UNSET:
            exceptions: list[SCMError] = []
            for error in response_body.errors:
                if error.type == "SCMCodedError":
                    exceptions.append(SCMCodedError(*error.details))
                elif error.type == "SCMProviderException":
                    exceptions.append(SCMProviderException(*error.details))
                elif error.type == "SCMError":
                    exceptions.append(SCMError(*error.details))
                else:
                    exceptions.append(
                        SCMUnhandledException(
                            f"Unknown error type: {error.type}", response.status_code, error.details
                        )
                    )
            if len(exceptions) == 1:
                raise exceptions[0]
            else:
                raise SCMUnhandledException(
                    "Multiple errors returned", response.status_code, exceptions
                )
        elif response_body.data is _Unset.UNSET:
            raise SCMUnhandledException(
                "Response did not match expected schema", response.status_code, response_json
            )
        else:
            if return_type is None:
                return None
            else:
                try:
                    return pydantic.parse_obj_as(return_type, response_body.data)
                except pydantic.ValidationError as e:
                    raise SCMUnhandledException(
                        "Response data did not match expected return type",
                        response.status_code,
                        response_json,
                    ) from e

    def get_issue_comments(self, issue_id: str) -> list[CommentActionResult]:
        return self._call(
            "get_issue_comments_v1", {"issue_id": issue_id}, list[CommentActionResult]
        )

    def create_issue_comment(self, issue_id: str, body: str) -> None:
        return self._call("create_issue_comment_v1", {"issue_id": issue_id, "body": body}, None)

    def delete_issue_comment(self, comment_id: str) -> None:
        return self._call("delete_issue_comment_v1", {"comment_id": comment_id}, None)

    def get_pull_request(self, pull_request_id: str) -> PullRequestActionResult:
        return self._call(
            "get_pull_request_v1", {"pull_request_id": pull_request_id}, PullRequestActionResult
        )

    def get_pull_request_comments(self, pull_request_id: str) -> list[CommentActionResult]:
        return self._call(
            "get_pull_request_comments_v1",
            {"pull_request_id": pull_request_id},
            list[CommentActionResult],
        )

    def create_pull_request_comment(self, pull_request_id: str, body: str) -> None:
        return self._call(
            "create_pull_request_comment_v1",
            {"pull_request_id": pull_request_id, "body": body},
            None,
        )

    def delete_pull_request_comment(self, comment_id: str) -> None:
        return self._call("delete_pull_request_comment_v1", {"comment_id": comment_id}, None)

    def get_issue_comment_reactions(self, comment_id: str) -> list[ReactionResult]:
        return self._call(
            "get_issue_comment_reactions_v1", {"comment_id": comment_id}, list[ReactionResult]
        )

    def create_issue_comment_reaction(self, comment_id: str, reaction: Reaction) -> None:
        return self._call(
            "create_issue_comment_reaction_v1",
            {"comment_id": comment_id, "reaction": reaction},
            None,
        )

    def delete_issue_comment_reaction(self, comment_id: str, reaction_id: str) -> None:
        return self._call(
            "delete_issue_comment_reaction_v1",
            {"comment_id": comment_id, "reaction_id": reaction_id},
            None,
        )

    def get_pull_request_comment_reactions(self, comment_id: str) -> list[ReactionResult]:
        return self._call(
            "get_pull_request_comment_reactions_v1",
            {"comment_id": comment_id},
            list[ReactionResult],
        )

    def create_pull_request_comment_reaction(self, comment_id: str, reaction: Reaction) -> None:
        return self._call(
            "create_pull_request_comment_reaction_v1",
            {"comment_id": comment_id, "reaction": reaction},
            None,
        )

    def delete_pull_request_comment_reaction(self, comment_id: str, reaction_id: str) -> None:
        return self._call(
            "delete_pull_request_comment_reaction_v1",
            {"comment_id": comment_id, "reaction_id": reaction_id},
            None,
        )

    def get_issue_reactions(self, issue_id: str) -> list[ReactionResult]:
        return self._call("get_issue_reactions_v1", {"issue_id": issue_id}, list[ReactionResult])

    def create_issue_reaction(self, issue_id: str, reaction: Reaction) -> None:
        return self._call(
            "create_issue_reaction_v1", {"issue_id": issue_id, "reaction": reaction}, None
        )

    def delete_issue_reaction(self, issue_id: str, reaction_id: str) -> None:
        return self._call(
            "delete_issue_reaction_v1", {"issue_id": issue_id, "reaction_id": reaction_id}, None
        )

    def get_pull_request_reactions(self, pull_request_id: str) -> list[ReactionResult]:
        return self._call(
            "get_pull_request_reactions_v1",
            {"pull_request_id": pull_request_id},
            list[ReactionResult],
        )

    def create_pull_request_reaction(self, pull_request_id: str, reaction: Reaction) -> None:
        return self._call(
            "create_pull_request_reaction_v1",
            {"pull_request_id": pull_request_id, "reaction": reaction},
            None,
        )

    def delete_pull_request_reaction(self, pull_request_id: str, reaction_id: str) -> None:
        return self._call(
            "delete_pull_request_reaction_v1",
            {"pull_request_id": pull_request_id, "reaction_id": reaction_id},
            None,
        )

    def get_branch(self, branch: str) -> GitRefActionResult:
        return self._call("get_branch_v1", {"branch": branch}, GitRefActionResult)

    def create_branch(self, branch: str, sha: str) -> GitRefActionResult:
        return self._call("create_branch_v1", {"branch": branch, "sha": sha}, GitRefActionResult)

    def update_branch(self, branch: str, sha: str, force: bool = False) -> None:
        return self._call("update_branch_v1", {"branch": branch, "sha": sha, "force": force}, None)

    def create_git_blob(self, content: str, encoding: str) -> GitBlobActionResult:
        return self._call(
            "create_git_blob_v1", {"content": content, "encoding": encoding}, GitBlobActionResult
        )

    def get_file_content(self, path: str, ref: str | None = None) -> FileContentActionResult:
        return self._call(
            "get_file_content_v1", {"path": path, "ref": ref}, FileContentActionResult
        )

    def get_commit(self, sha: str) -> CommitActionResult:
        return self._call("get_commit_v1", {"sha": sha}, CommitActionResult)

    def get_commits(
        self, *, sha: str | None = None, path: str | None = None
    ) -> list[CommitActionResult]:
        return self._call("get_commits_v1", {"sha": sha, "path": path}, list[CommitActionResult])

    def compare_commits(self, start_sha: str, end_sha: str) -> CommitComparisonActionResult:
        return self._call(
            "compare_commits_v1",
            {"start_sha": start_sha, "end_sha": end_sha},
            CommitComparisonActionResult,
        )

    def get_tree(self, tree_sha: str, *, recursive: bool = True) -> GitTreeActionResult:
        return self._call(
            "get_tree_v1", {"tree_sha": tree_sha, "recursive": recursive}, GitTreeActionResult
        )

    def get_git_commit(self, sha: str) -> GitCommitObjectActionResult:
        return self._call("get_git_commit_v1", {"sha": sha}, GitCommitObjectActionResult)

    def create_git_tree(
        self, tree: list[InputTreeEntry], *, base_tree: str | None = None
    ) -> GitTreeActionResult:
        return self._call(
            "create_git_tree_v1",
            {"tree": [entry.dict() for entry in tree], "base_tree": base_tree},
            GitTreeActionResult,
        )

    def create_git_commit(
        self, message: str, tree_sha: str, parent_shas: list[str]
    ) -> GitCommitObjectActionResult:
        return self._call(
            "create_git_commit_v1",
            {"message": message, "tree_sha": tree_sha, "parent_shas": parent_shas},
            GitCommitObjectActionResult,
        )

    def get_pull_request_files(self, pull_request_id: str) -> PullRequestFileActionResult:
        return self._call(
            "get_pull_request_files_v1",
            {"pull_request_id": pull_request_id},
            PullRequestFileActionResult,
        )

    def get_pull_request_commits(self, pull_request_id: str) -> PullRequestCommitActionResult:
        return self._call(
            "get_pull_request_commits_v1",
            {"pull_request_id": pull_request_id},
            PullRequestCommitActionResult,
        )

    def get_pull_request_diff(self, pull_request_id: str) -> PullRequestDiffActionResult:
        return self._call(
            "get_pull_request_diff_v1",
            {"pull_request_id": pull_request_id},
            PullRequestDiffActionResult,
        )

    def list_pull_requests(
        self, state: str = "open", head: str | None = None
    ) -> list[PullRequestActionResult]:
        return self._call(
            "list_pull_requests_v1", {"state": state, "head": head}, list[PullRequestActionResult]
        )

    def create_pull_request(
        self, title: str, body: str, head: str, base: str, *, draft: bool = False
    ) -> PullRequestActionResult:
        return self._call(
            "create_pull_request_v1",
            {"title": title, "body": body, "head": head, "base": base, "draft": draft},
            PullRequestActionResult,
        )

    def update_pull_request(
        self,
        pull_request_id: str,
        *,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
    ) -> PullRequestActionResult:
        return self._call(
            "update_pull_request_v1",
            {"pull_request_id": pull_request_id, "title": title, "body": body, "state": state},
            PullRequestActionResult,
        )

    def request_review(self, pull_request_id: str, reviewers: list[str]) -> None:
        return self._call(
            "request_review_v1", {"pull_request_id": pull_request_id, "reviewers": reviewers}, None
        )

    def create_review_comment(
        self,
        pull_request_id: str,
        body: str,
        commit_sha: str,
        path: str,
        *,
        line: int | None = None,
        side: str | None = None,
        start_line: int | None = None,
        start_side: str | None = None,
    ) -> ReviewCommentActionResult:
        return self._call(
            "create_review_comment_v1",
            {
                "pull_request_id": pull_request_id,
                "body": body,
                "commit_sha": commit_sha,
                "path": path,
                "line": line,
                "side": side,
                "start_line": start_line,
                "start_side": start_side,
            },
            ReviewCommentActionResult,
        )

    def create_review(
        self,
        pull_request_id: str,
        commit_sha: str,
        event: str,
        comments: list[ReviewCommentInput],
        *,
        body: str | None = None,
    ) -> ReviewActionResult:
        return self._call(
            "create_review_v1",
            {
                "pull_request_id": pull_request_id,
                "commit_sha": commit_sha,
                "event": event,
                "comments": [c.dict() for c in comments],
                "body": body,
            },
            ReviewActionResult,
        )

    def create_check_run(
        self,
        name: str,
        head_sha: str,
        *,
        status: str | None = None,
        conclusion: str | None = None,
        external_id: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
        output: CheckRunOutput | None = None,
    ) -> CheckRunActionResult:
        return self._call(
            "create_check_run_v1",
            {
                "name": name,
                "head_sha": head_sha,
                "status": status,
                "conclusion": conclusion,
                "external_id": external_id,
                "started_at": started_at,
                "completed_at": completed_at,
                "output": output.dict() if output else None,
            },
            CheckRunActionResult,
        )

    def get_check_run(self, check_run_id: str) -> CheckRunActionResult:
        return self._call("get_check_run_v1", {"check_run_id": check_run_id}, CheckRunActionResult)

    def update_check_run(
        self,
        check_run_id: str,
        *,
        status: str | None = None,
        conclusion: str | None = None,
        output: CheckRunOutput | None = None,
    ) -> CheckRunActionResult:
        return self._call(
            "update_check_run_v1",
            {
                "check_run_id": check_run_id,
                "status": status,
                "conclusion": conclusion,
                "output": output.dict() if output else None,
            },
            CheckRunActionResult,
        )

    def minimize_comment(self, comment_node_id: str, reason: str) -> None:
        return self._call(
            "minimize_comment_v1", {"comment_node_id": comment_node_id, "reason": reason}, None
        )

    def resolve_review_thread(self, thread_node_id: str) -> None:
        return self._call("resolve_review_thread_v1", {"thread_node_id": thread_node_id}, None)
