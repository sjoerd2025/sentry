from collections.abc import Callable
from typing import Any, NamedTuple

import pydantic
import pytest
import requests
import responses.matchers

from sentry.scm.client.errors import (
    SCMCodedError,
    SCMError,
    SCMProviderException,
    SCMUnhandledException,
)
from sentry.scm.client.scm_rpc_client import SourceCodeManagerRPCClient
from sentry.scm.client.types import (
    Author,
    CheckRun,
    CheckRunActionResult,
    CheckRunOutput,
    Comment,
    CommentActionResult,
    Commit,
    CommitActionResult,
    CommitAuthor,
    CommitComparison,
    CommitComparisonActionResult,
    CommitFile,
    FileContent,
    FileContentActionResult,
    GitBlob,
    GitBlobActionResult,
    GitCommitObject,
    GitCommitObjectActionResult,
    GitCommitTree,
    GitRef,
    GitRefActionResult,
    GitTree,
    GitTreeActionResult,
    InputTreeEntry,
    PullRequest,
    PullRequestActionResult,
    PullRequestBranch,
    PullRequestCommit,
    PullRequestCommitActionResult,
    PullRequestDiffActionResult,
    PullRequestFile,
    PullRequestFileActionResult,
    ReactionResult,
    Review,
    ReviewActionResult,
    ReviewComment,
    ReviewCommentActionResult,
    ReviewCommentInput,
    TreeEntry,
)

shared_secret = "test-shared-secret"
base_url = "http://testserver"
prefix = "api/0/internal/scm-rpc"


@pytest.fixture
def client() -> SourceCodeManagerRPCClient:
    return SourceCodeManagerRPCClient(
        base_url=base_url,
        shared_secret=shared_secret,
        organization_id=123,
        repository_id=456,
    )


@responses.activate
def test_request_is_signed(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/create_issue_comment_v1/",
        match=[
            responses.matchers.header_matcher(
                {
                    "Authorization": "rpcsignature rpc0:f5972f8189569e92b071bd3b4f80b80ae9e2617b6c6fc4594ff44f42c8c732ea"
                }
            ),
        ],
        json={"data": None},
    )
    client.create_issue_comment("test-issue-id", "body")
    responses.assert_call_count(f"{base_url}/{prefix}/create_issue_comment_v1/", 1)


@responses.activate
def test_additional_fields_in_rpc_response_are_ignored(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        match=[
            responses.matchers.json_params_matcher(
                {
                    "args": {
                        "issue_id": "test-issue-id",
                        "organization_id": 123,
                        "repository_id": 456,
                    }
                }
            ),
        ],
        json={
            "data": [
                {
                    "comment": {
                        "id": "test-comment-id",
                        "body": "test comment",
                        "author": {"id": "test-author-id", "username": "test author", "foo": "bar"},
                        "additional": "field",
                    },
                    "provider": "test provider",
                    "raw": {"foo": "bar"},
                    "bar": "baz",
                }
            ]
        },
    )
    assert client.get_issue_comments("test-issue-id") == [
        CommentActionResult(
            comment=Comment(
                id="test-comment-id",
                body="test comment",
                author=Author(
                    id="test-author-id",
                    username="test author",
                ),
            ),
            provider="test provider",
            raw={"foo": "bar"},
        )
    ]
    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)


@responses.activate
def test_provided_session_is_used():
    session = requests.Session()
    session.headers["X-Test-Header"] = "test value"
    client = SourceCodeManagerRPCClient(
        base_url=base_url,
        shared_secret=shared_secret,
        organization_id=123,
        repository_id=456,
        session=session,
    )
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/create_issue_comment_v1/",
        # The custom header from the provided session is included in the request
        match=[
            responses.matchers.header_matcher(
                {
                    "X-Test-Header": "test value",
                }
            ),
        ],
        json={"data": None},
    )
    client.create_issue_comment("test-issue-id", "body")
    responses.assert_call_count(f"{base_url}/{prefix}/create_issue_comment_v1/", 1)


class SimpleSuccessTest(NamedTuple):
    method: Callable
    args: dict[str, Any]
    kwargs: dict[str, Any]
    expected_url: str
    expected_result: Any


@pytest.mark.parametrize(
    "param",
    [
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_issue_comments,
            {"issue_id": "test-issue-id"},
            {},
            f"{base_url}/{prefix}/get_issue_comments_v1/",
            [
                CommentActionResult(
                    comment=Comment(
                        id="test-comment-id",
                        body="test comment",
                        author=Author(
                            id="test-author-id",
                            username="test author",
                        ),
                    ),
                    provider="test provider",
                    raw={"foo": "bar"},
                )
            ],
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_issue_comment,
            {"issue_id": "test-issue-id", "body": "test comment body"},
            {},
            f"{base_url}/{prefix}/create_issue_comment_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.delete_issue_comment,
            {"comment_id": "comment-id"},
            {},
            f"{base_url}/{prefix}/delete_issue_comment_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_pull_request,
            {"pull_request_id": "pull-request-id"},
            {},
            f"{base_url}/{prefix}/get_pull_request_v1/",
            PullRequestActionResult(
                pull_request=PullRequest(
                    id=1,
                    number=2,
                    title="test pr",
                    body="test pr body",
                    state="open",
                    merged=False,
                    url="http://example.com/pr",
                    html_url="http://example.com/pr",
                    head=PullRequestBranch(sha="head-sha", ref="head-ref"),
                    base=PullRequestBranch(sha="base-sha", ref="base-ref"),
                ),
                provider="test provider",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_pull_request_comments,
            dict(pull_request_id="pull-request-id"),
            {},
            f"{base_url}/{prefix}/get_pull_request_comments_v1/",
            [
                CommentActionResult(
                    comment=Comment(
                        id="test-comment-id",
                        body="test comment",
                        author=Author(id="test-author-id", username="test author"),
                    ),
                    provider="test provider",
                    raw={"foo": "bar"},
                )
            ],
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_pull_request_comment,
            {"pull_request_id": "pull-request-id", "body": "comment body"},
            {},
            f"{base_url}/{prefix}/create_pull_request_comment_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.delete_pull_request_comment,
            {"comment_id": "comment-id"},
            {},
            f"{base_url}/{prefix}/delete_pull_request_comment_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_issue_comment_reactions,
            dict(comment_id="comment-id"),
            {},
            f"{base_url}/{prefix}/get_issue_comment_reactions_v1/",
            [
                ReactionResult(
                    id="reaction-id",
                    content="+1",
                    author=Author(id="author-id", username="author-username"),
                )
            ],
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_issue_comment_reaction,
            {"comment_id": "comment-id", "reaction": "+1"},
            {},
            f"{base_url}/{prefix}/create_issue_comment_reaction_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.delete_issue_comment_reaction,
            {"comment_id": "comment-id", "reaction_id": "reaction-id"},
            {},
            f"{base_url}/{prefix}/delete_issue_comment_reaction_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_pull_request_comment_reactions,
            dict(comment_id="comment-id"),
            {},
            f"{base_url}/{prefix}/get_pull_request_comment_reactions_v1/",
            [
                ReactionResult(
                    id="reaction-id",
                    content="+1",
                    author=Author(id="test-author-id", username="test-author"),
                )
            ],
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_pull_request_comment_reaction,
            {"comment_id": "comment-id", "reaction": "+1"},
            {},
            f"{base_url}/{prefix}/create_pull_request_comment_reaction_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.delete_pull_request_comment_reaction,
            {"comment_id": "comment-id", "reaction_id": "reaction-id"},
            {},
            f"{base_url}/{prefix}/delete_pull_request_comment_reaction_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_issue_reactions,
            dict(issue_id="issue-id"),
            {},
            f"{base_url}/{prefix}/get_issue_reactions_v1/",
            [
                ReactionResult(
                    id="reaction-id",
                    content="+1",
                    author=Author(id="test-author-id", username="test-author"),
                )
            ],
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_issue_reaction,
            {"issue_id": "issue-id", "reaction": "+1"},
            {},
            f"{base_url}/{prefix}/create_issue_reaction_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.delete_issue_reaction,
            {"issue_id": "issue-id", "reaction_id": "reaction-id"},
            {},
            f"{base_url}/{prefix}/delete_issue_reaction_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_pull_request_reactions,
            dict(pull_request_id="pull-request-id"),
            {},
            f"{base_url}/{prefix}/get_pull_request_reactions_v1/",
            [
                ReactionResult(
                    id="reaction-id",
                    content="+1",
                    author=Author(id="test-author-id", username="test-author"),
                )
            ],
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_pull_request_reaction,
            {"pull_request_id": "pull-request-id", "reaction": "+1"},
            {},
            f"{base_url}/{prefix}/create_pull_request_reaction_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.delete_pull_request_reaction,
            {"pull_request_id": "pull-request-id", "reaction_id": "reaction-id"},
            {},
            f"{base_url}/{prefix}/delete_pull_request_reaction_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_branch,
            {"branch": "branch-name"},
            {},
            f"{base_url}/{prefix}/get_branch_v1/",
            GitRefActionResult(
                git_ref=GitRef(ref="ref", sha="sha"), provider="github", raw={"foo": "bar"}
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_branch,
            {"branch": "branch-name", "sha": "sha"},
            {},
            f"{base_url}/{prefix}/create_branch_v1/",
            GitRefActionResult(
                git_ref=GitRef(ref="ref", sha="sha"), provider="github", raw={"foo": "bar"}
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.update_branch,
            {"branch": "branch", "sha": "sha"},
            {"force": False},
            f"{base_url}/{prefix}/update_branch_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_git_blob,
            {"content": "content", "encoding": "utf-8"},
            {},
            f"{base_url}/{prefix}/create_git_blob_v1/",
            GitBlobActionResult(git_blob=GitBlob(sha="sha"), provider="github", raw={"foo": "bar"}),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_file_content,
            {"path": "file-path", "ref": "ref"},
            {},
            f"{base_url}/{prefix}/get_file_content_v1/",
            FileContentActionResult(
                file_content=FileContent(
                    path="file-path", sha="sha", content="file content", encoding="utf-8", size=42
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_commit,
            {"sha": "sha"},
            {},
            f"{base_url}/{prefix}/get_commit_v1/",
            CommitActionResult(
                commit=Commit(
                    sha="sha",
                    message="message",
                    author=CommitAuthor(
                        name="author", email="author@example.com", date="2024-06-01T00:00:00Z"
                    ),
                    files=[CommitFile(filename="filename", status="status", patch="patch")],
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_commits,
            {},
            dict(sha=None, path=None),
            f"{base_url}/{prefix}/get_commits_v1/",
            [
                CommitActionResult(
                    commit=Commit(
                        sha="sha",
                        message="message",
                        author=CommitAuthor(
                            name="author", email="author@example.com", date="2024-06-01T00:00:00Z"
                        ),
                        files=[CommitFile(filename="filename", status="status", patch="patch")],
                    ),
                    provider="github",
                    raw={"foo": "bar"},
                )
            ],
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.compare_commits,
            {"start_sha": "start", "end_sha": "end"},
            {},
            f"{base_url}/{prefix}/compare_commits_v1/",
            CommitComparisonActionResult(
                comparison=CommitComparison(ahead_by=1, behind_by=2),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_tree,
            {"tree_sha": "sha"},
            {"recursive": True},
            f"{base_url}/{prefix}/get_tree_v1/",
            GitTreeActionResult(
                git_tree=GitTree(
                    tree=[TreeEntry(path="file-path", mode="100644", type="blob", sha="sha")],
                    truncated=True,
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_git_commit,
            {"sha": "sha"},
            {},
            f"{base_url}/{prefix}/get_git_commit_v1/",
            GitCommitObjectActionResult(
                git_commit=GitCommitObject(
                    sha="sha", tree=GitCommitTree(sha="tree-sha"), message="message"
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_git_tree,
            {"tree": [InputTreeEntry(path="path", mode="mode", type="type", sha="sha")]},
            {"base_tree": "base"},
            f"{base_url}/{prefix}/create_git_tree_v1/",
            GitTreeActionResult(
                git_tree=GitTree(
                    tree=[TreeEntry(path="file-path", mode="100644", type="blob", sha="sha")],
                    truncated=True,
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_git_commit,
            {"message": "message", "tree_sha": "tree", "parent_shas": ["sha-1", "sha-2"]},
            {},
            f"{base_url}/{prefix}/create_git_commit_v1/",
            GitCommitObjectActionResult(
                git_commit=GitCommitObject(
                    sha="sha", tree=GitCommitTree(sha="tree-sha"), message="message"
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_pull_request_files,
            {"pull_request_id": "pull-request-id"},
            {},
            f"{base_url}/{prefix}/get_pull_request_files_v1/",
            PullRequestFileActionResult(
                files=[
                    PullRequestFile(
                        filename="filename",
                        status="status",
                        patch="patch",
                        changes=3,
                        sha="sha",
                        previous_filename="previous-name",
                    )
                ],
                provider="github",
                raw=[{"foo": "bar"}],
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_pull_request_commits,
            {"pull_request_id": "pr-id"},
            {},
            f"{base_url}/{prefix}/get_pull_request_commits_v1/",
            PullRequestCommitActionResult(
                commits=[
                    PullRequestCommit(
                        sha="sha",
                        message="message",
                        author=CommitAuthor(
                            name="author", email="blah@foo.com", date="2024-06-01T00:00:00Z"
                        ),
                    )
                ],
                provider="github",
                raw=[{"foo": "bar"}],
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_pull_request_diff,
            {"pull_request_id": "pr-id"},
            {},
            f"{base_url}/{prefix}/get_pull_request_diff_v1/",
            PullRequestDiffActionResult(diff="diff content", provider="github"),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.list_pull_requests,
            {"state": "open", "head": None},
            {},
            f"{base_url}/{prefix}/list_pull_requests_v1/",
            [
                PullRequestActionResult(
                    pull_request=PullRequest(
                        id=1,
                        number=2,
                        title="test pr",
                        body="test pr body",
                        state="open",
                        merged=False,
                        url="http://example.com/pr",
                        html_url="http://example.com/pr",
                        head=PullRequestBranch(sha="head-sha", ref="head-ref"),
                        base=PullRequestBranch(sha="base-sha", ref="base-ref"),
                    ),
                    provider="test provider",
                    raw={"foo": "bar"},
                )
            ],
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_pull_request,
            {
                "title": "title",
                "body": "body",
                "head": "head",
                "base": "base",
            },
            {"draft": False},
            f"{base_url}/{prefix}/create_pull_request_v1/",
            PullRequestActionResult(
                pull_request=PullRequest(
                    id=1,
                    number=2,
                    title="test pr",
                    body="test pr body",
                    state="open",
                    merged=False,
                    url="http://example.com/pr",
                    html_url="http://example.com/pr",
                    head=PullRequestBranch(sha="head-sha", ref="head-ref"),
                    base=PullRequestBranch(sha="base-sha", ref="base-ref"),
                ),
                provider="test provider",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.update_pull_request,
            {"pull_request_id": "pr-id"},
            {"title": "title", "body": "body", "state": "state"},
            f"{base_url}/{prefix}/update_pull_request_v1/",
            PullRequestActionResult(
                pull_request=PullRequest(
                    id=1,
                    number=2,
                    title="test pr",
                    body="test pr body",
                    state="open",
                    merged=False,
                    url="http://example.com/pr",
                    html_url="http://example.com/pr",
                    head=PullRequestBranch(sha="head-sha", ref="head-ref"),
                    base=PullRequestBranch(sha="base-sha", ref="base-ref"),
                ),
                provider="test provider",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.request_review,
            {"pull_request_id": "pull-request-id", "reviewers": ["reviewer1", "reviewer2"]},
            {},
            f"{base_url}/{prefix}/request_review_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_review_comment,
            {
                "pull_request_id": "pr-id",
                "body": "body",
                "commit_sha": "sha",
                "path": "path",
            },
            {"line": 42, "side": "LEFT", "start_line": 57, "start_side": "right"},
            f"{base_url}/{prefix}/create_review_comment_v1/",
            ReviewCommentActionResult(
                review_comment=ReviewComment(
                    id=73, html_url="http://blah", path="path", body="comment body"
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_review,
            {
                "pull_request_id": "pr-id",
                "commit_sha": "sha",
                "event": "frob",
                "comments": [
                    ReviewCommentInput(
                        path="path", body="body", line=42, start_line=57, start_side="left"
                    )
                ],
            },
            {"body": "body"},
            f"{base_url}/{prefix}/create_review_v1/",
            ReviewActionResult(
                review=Review(id=73, html_url="http://blah"), provider="github", raw={"foo": "bar"}
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.create_check_run,
            {"name": "name", "head_sha": "sha"},
            {
                "status": "status",
                "conclusion": "ok",
                "external_id": "blah",
                "started_at": "",
                "completed_at": "",
                "output": CheckRunOutput(title="title", summary="summary", text="text"),
            },
            f"{base_url}/{prefix}/create_check_run_v1/",
            CheckRunActionResult(
                check_run=CheckRun(
                    id=73, name="name", status="status", conclusion="ok", html_url="http://blah"
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.get_check_run,
            {"check_run_id": "chk-id"},
            {},
            f"{base_url}/{prefix}/get_check_run_v1/",
            CheckRunActionResult(
                check_run=CheckRun(
                    id=73, name="name", status="status", conclusion="ok", html_url="http://blah"
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.update_check_run,
            {"check_run_id": "chk-id"},
            {
                "status": "status",
                "conclusion": "ok",
                "output": CheckRunOutput(title="title", summary="summary", text="text"),
            },
            f"{base_url}/{prefix}/update_check_run_v1/",
            CheckRunActionResult(
                check_run=CheckRun(
                    id=73, name="name", status="status", conclusion="ok", html_url="http://blah"
                ),
                provider="github",
                raw={"foo": "bar"},
            ),
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.minimize_comment,
            {"comment_node_id": "comment-node-id", "reason": "reason"},
            {},
            f"{base_url}/{prefix}/minimize_comment_v1/",
            None,
        ),
        SimpleSuccessTest(
            SourceCodeManagerRPCClient.resolve_review_thread,
            {},
            {"thread_node_id": "thread-node-id"},
            f"{base_url}/{prefix}/resolve_review_thread_v1/",
            None,
        ),
    ],
    ids=lambda param: param.expected_url.split("/")[-2],
)
@responses.activate
def test_simple_success(
    client: SourceCodeManagerRPCClient,
    param: SimpleSuccessTest,
):
    data: Any
    if param.expected_result is None:
        data = None
    elif isinstance(param.expected_result, list):
        assert len(param.expected_result) != 0
        assert all(isinstance(item, pydantic.BaseModel) for item in param.expected_result)
        data = [item.dict() for item in param.expected_result]
    else:
        assert isinstance(param.expected_result, pydantic.BaseModel)
        data = param.expected_result.dict()

    responses.add(
        responses.POST,
        param.expected_url,
        match=[
            responses.matchers.json_params_matcher(
                {
                    "args": {
                        "organization_id": 123,
                        "repository_id": 456,
                    }
                    | param.args
                    | param.kwargs
                }
            ),
        ],
        json={"data": data},
    )
    # With all keywords arguments
    assert param.method(client, *param.args.values(), **param.kwargs) == param.expected_result
    # With mostly positional arguments
    assert param.method(client, **param.args, **param.kwargs) == param.expected_result
    responses.assert_call_count(param.expected_url, 2)


@responses.activate
def test_non_json_response_raises_unhandled_exception(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        status=299,
        body="non-json response",
    )
    with pytest.raises(SCMUnhandledException) as exc:
        client.get_issue_comments("test-issue-id")
    assert exc.value.args == ("Response was not JSON", 299, "non-json response")
    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)


@responses.activate
def test_invalid_json_response_raises_unhandled_exception(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        status=299,
        json={"errors": 42},
    )
    with pytest.raises(SCMUnhandledException) as exc:
        client.get_issue_comments("test-issue-id")
    assert exc.value.args == ("Response did not match expected schema", 299, {"errors": 42})
    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)


@responses.activate
def test_empty_response_raises_unhandled_exception(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        status=299,
        json={},
    )
    with pytest.raises(SCMUnhandledException) as exc:
        client.get_issue_comments("test-issue-id")
    assert exc.value.args == ("Response did not match expected schema", 299, {})
    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)


@responses.activate
def test_invalid_json_response_data_raises_unhandled_exception(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        status=299,
        json={"data": [{"foo": "bar"}]},
    )
    with pytest.raises(SCMUnhandledException) as exc:
        client.get_issue_comments("test-issue-id")
    assert exc.value.args == (
        "Response data did not match expected return type",
        299,
        {"data": [{"foo": "bar"}]},
    )
    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)


@responses.activate
def test_scm_coded_error_is_raised_as_is(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        json={
            "errors": [
                {
                    "type": "SCMCodedError",
                    "details": [
                        "repository_not_found",
                        "A repository could not be found.",
                        "Blah",
                        68,
                    ],
                }
            ]
        },
        status=400,
    )
    with pytest.raises(SCMCodedError) as exc:
        client.get_issue_comments("test-issue-id")
    assert exc.value.args == (
        "repository_not_found",
        "A repository could not be found.",
        "Blah",
        68,
    )
    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)


@responses.activate
def test_multiple_errors_raises_unhandled_exception(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        json={
            "errors": [
                {
                    "type": "SCMCodedError",
                    "details": [
                        "repository_not_found",
                        "A repository could not be found.",
                        "Blah",
                        68,
                    ],
                },
                {
                    "type": "SCMCodedError",
                    "details": [
                        "repository_not_found",
                        "A repository could not be found.",
                        "Blah",
                        68,
                    ],
                },
            ]
        },
        status=400,
    )
    with pytest.raises(SCMUnhandledException) as exc:
        client.get_issue_comments("test-issue-id")
    assert len(exc.value.args) == 3
    assert exc.value.args[0] == "Multiple errors returned"
    assert exc.value.args[1] == 400
    assert len(exc.value.args[2]) == 2
    assert exc.value.args[2][0].args == (
        "repository_not_found",
        "A repository could not be found.",
        "Blah",
        68,
    )
    assert exc.value.args[2][1].args == (
        "repository_not_found",
        "A repository could not be found.",
        "Blah",
        68,
    )

    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)


@responses.activate
def test_scm_provider_exception_is_raised_as_is(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        json={
            "errors": [
                {
                    "type": "SCMProviderException",
                    "details": [
                        "A provider error occurred.",
                        "Blah",
                        68,
                    ],
                }
            ]
        },
        status=500,
    )
    with pytest.raises(SCMProviderException) as exc:
        client.get_issue_comments("test-issue-id")
    assert exc.value.args == (
        "A provider error occurred.",
        "Blah",
        68,
    )
    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)


@responses.activate
def test_scm_error_is_raised_as_is(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        json={
            "errors": [
                {
                    "type": "SCMError",
                    "details": [
                        "A generic SCM error occurred.",
                        "Blah",
                        68,
                    ],
                }
            ]
        },
        status=500,
    )
    with pytest.raises(SCMError) as exc:
        client.get_issue_comments("test-issue-id")
    assert exc.value.args == (
        "A generic SCM error occurred.",
        "Blah",
        68,
    )
    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)


@responses.activate
def test_unknown_error_type_raises_unhandled_exception(client: SourceCodeManagerRPCClient):
    responses.add(
        responses.POST,
        f"{base_url}/{prefix}/get_issue_comments_v1/",
        json={
            "errors": [
                {
                    "type": "UnknownErrorType",
                    "details": [
                        "Some unknown error occurred.",
                        "Blah",
                        68,
                    ],
                }
            ]
        },
        status=299,
    )
    with pytest.raises(SCMUnhandledException) as exc:
        client.get_issue_comments("test-issue-id")
    assert exc.value.args == (
        "Unknown error type: UnknownErrorType",
        299,
        [
            "Some unknown error occurred.",
            "Blah",
            68,
        ],
    )
    responses.assert_call_count(f"{base_url}/{prefix}/get_issue_comments_v1/", 1)
