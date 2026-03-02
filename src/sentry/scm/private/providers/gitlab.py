import datetime
import functools
from typing import Any

from sentry.integrations.gitlab.client import GitLabApiClient
from sentry.scm.errors import SCMProviderException
from sentry.scm.types import (
    ActionResult,
    BuildConclusion,
    BuildStatus,
    CheckRun,
    CheckRunOutput,
    Comment,
    Commit,
    CommitAuthor,
    CommitComparison,
    FileContent,
    GitBlob,
    GitCommitObject,
    GitRef,
    GitTree,
    InputTreeEntry,
    PullRequest,
    PullRequestBranch,
    PullRequestCommit,
    PullRequestFile,
    Reaction,
    ReactionResult,
    Referrer,
    Repository,
    Review,
    ReviewComment,
    ReviewCommentInput,
    ReviewSide,
)
from sentry.shared_integrations.exceptions import ApiError

# TODO: Rate-limits are dynamic per org. Some will have higher limits. We need to dynamically
#       configure the shared pool. The absolute allocation amount for explicit referrers can
#       remain unchanged.
REFERRER_ALLOCATION: dict[Referrer, int] = {"shared": 4500, "emerge": 500}


def catch_provider_exception(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ApiError as e:
            raise SCMProviderException(str(e)) from e

    return wrapper


class GitLabProvider:
    def __init__(self, client: GitLabApiClient, repository: Repository) -> None:
        self.client = client
        self.repository = repository
        external_id = repository["external_id"]
        assert external_id is not None
        prefix = "gitlab.com:"
        assert external_id.startswith(prefix)
        self._repo_id = external_id[len(prefix) :]

    def is_rate_limited(self, organization_id: int, referrer: Referrer) -> bool:
        from sentry.scm.helpers import is_rate_limited_with_allocation_policy

        return is_rate_limited_with_allocation_policy(
            organization_id,
            referrer,
            provider="gitlab",
            window=3600,
            allocation_policy=REFERRER_ALLOCATION,
        )

    def get_pull_request(self, pull_request_id: str) -> ActionResult[PullRequest]:
        raw = self.client.get_merge_request(self._repo_id, pull_request_id)
        return ActionResult(
            data=PullRequest(
                id=raw["id"],
                number=raw["iid"],
                title=raw["title"],
                body=raw["description"] or None,
                state="open",
                base=PullRequestBranch(ref=raw["target_branch"], sha=None),
                head=PullRequestBranch(
                    ref=raw["source_branch"],
                    sha=raw["sha"],
                ),
                merged=raw["merged_at"] is not None,
                html_url=raw["web_url"],
            ),
            type="gitlab",
            raw=raw,
        )

    def get_issue_comments(self, issue_id: str) -> ActionResult[list[Comment]]:
        raise NotImplementedError

    def create_issue_comment(self, issue_id: str, body: str) -> ActionResult[Comment]:
        raise NotImplementedError

    def delete_issue_comment(self, comment_id: str) -> None:
        raise NotImplementedError

    def get_pull_request_comments(self, pull_request_id: str) -> ActionResult[list[Comment]]:
        raise NotImplementedError

    def create_pull_request_comment(self, pull_request_id: str, body: str) -> ActionResult[Comment]:
        raise NotImplementedError

    def delete_pull_request_comment(self, comment_id: str) -> None:
        raise NotImplementedError

    def get_issue_comment_reactions(self, comment_id: str) -> ActionResult[list[ReactionResult]]:
        raise NotImplementedError

    def create_issue_comment_reaction(
        self, comment_id: str, reaction: Reaction
    ) -> ActionResult[ReactionResult]:
        raise NotImplementedError

    def delete_issue_comment_reaction(self, comment_id: str, reaction_id: str) -> None:
        raise NotImplementedError

    def get_pull_request_comment_reactions(
        self, comment_id: str
    ) -> ActionResult[list[ReactionResult]]:
        raise NotImplementedError

    def create_pull_request_comment_reaction(
        self, comment_id: str, reaction: Reaction
    ) -> ActionResult[ReactionResult]:
        raise NotImplementedError

    def delete_pull_request_comment_reaction(self, comment_id: str, reaction_id: str) -> None:
        raise NotImplementedError

    def get_issue_reactions(self, issue_id: str) -> ActionResult[list[ReactionResult]]:
        raise NotImplementedError

    def create_issue_reaction(
        self, issue_id: str, reaction: Reaction
    ) -> ActionResult[ReactionResult]:
        raise NotImplementedError

    def delete_issue_reaction(self, issue_id: str, reaction_id: str) -> None:
        raise NotImplementedError

    def get_pull_request_reactions(
        self, pull_request_id: str
    ) -> ActionResult[list[ReactionResult]]:
        raise NotImplementedError

    def create_pull_request_reaction(
        self, pull_request_id: str, reaction: Reaction
    ) -> ActionResult[ReactionResult]:
        raise NotImplementedError

    def delete_pull_request_reaction(self, pull_request_id: str, reaction_id: str) -> None:
        raise NotImplementedError

    def get_branch(self, branch: str) -> ActionResult[GitRef]:
        raise NotImplementedError

    def create_branch(self, branch: str, sha: str) -> ActionResult[GitRef]:
        raise NotImplementedError

    def update_branch(self, branch: str, sha: str, force: bool = False) -> None:
        raise NotImplementedError

    def create_git_blob(self, content: str, encoding: str) -> ActionResult[GitBlob]:
        raise NotImplementedError

    def get_file_content(self, path: str, ref: str | None = None) -> ActionResult[FileContent]:
        raise NotImplementedError

    def get_commit(self, sha: str) -> ActionResult[Commit]:
        raise NotImplementedError

    @catch_provider_exception
    def get_commits(
        self,
        sha: str | None = None,
        path: str | None = None,
    ) -> ActionResult[list[Commit]]:
        raw_commits = self.client.get_last_commits(self._repo_id, end_sha=sha)
        return ActionResult(
            data=[map_commit(c) for c in raw_commits],
            type="gitlab",
            raw={"items": raw_commits},
        )

    def compare_commits(self, start_sha: str, end_sha: str) -> ActionResult[CommitComparison]:
        raise NotImplementedError

    def get_tree(self, tree_sha: str, recursive: bool = True) -> ActionResult[GitTree]:
        raise NotImplementedError

    def get_git_commit(self, sha: str) -> ActionResult[GitCommitObject]:
        raise NotImplementedError

    def create_git_tree(
        self, tree: list[InputTreeEntry], base_tree: str | None = None
    ) -> ActionResult[GitTree]:
        raise NotImplementedError

    def create_git_commit(
        self, message: str, tree_sha: str, parent_shas: list[str]
    ) -> ActionResult[GitCommitObject]:
        raise NotImplementedError

    def get_pull_request_files(self, pull_request_id: str) -> ActionResult[list[PullRequestFile]]:
        raise NotImplementedError

    def get_pull_request_commits(
        self, pull_request_id: str
    ) -> ActionResult[list[PullRequestCommit]]:
        raise NotImplementedError

    def get_pull_request_diff(self, pull_request_id: str) -> ActionResult[str]:
        raise NotImplementedError

    def get_pull_requests(
        self, state: str = "open", head: str | None = None
    ) -> ActionResult[list[PullRequest]]:
        raise NotImplementedError

    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = False,
    ) -> ActionResult[PullRequest]:
        raise NotImplementedError

    def update_pull_request(
        self,
        pull_request_id: str,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
    ) -> ActionResult[PullRequest]:
        raise NotImplementedError

    def request_review(self, pull_request_id: str, reviewers: list[str]) -> None:
        raise NotImplementedError

    def create_review_comment(
        self,
        pull_request_id: str,
        body: str,
        commit_sha: str,
        path: str,
        line: int | None = None,
        side: ReviewSide | None = None,
        start_line: int | None = None,
        start_side: ReviewSide | None = None,
    ) -> ActionResult[ReviewComment]:
        raise NotImplementedError

    def create_review(
        self,
        pull_request_id: str,
        commit_sha: str,
        event: str,
        comments: list[ReviewCommentInput],
        body: str | None = None,
    ) -> ActionResult[Review]:
        raise NotImplementedError

    def create_check_run(
        self,
        name: str,
        head_sha: str,
        status: BuildStatus | None = None,
        conclusion: BuildConclusion | None = None,
        external_id: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
        output: CheckRunOutput | None = None,
    ) -> ActionResult[CheckRun]:
        raise NotImplementedError

    def get_check_run(self, check_run_id: str) -> ActionResult[CheckRun]:
        raise NotImplementedError

    def update_check_run(
        self,
        check_run_id: str,
        status: BuildStatus | None = None,
        conclusion: BuildConclusion | None = None,
        output: CheckRunOutput | None = None,
    ) -> ActionResult[CheckRun]:
        raise NotImplementedError

    def minimize_comment(self, comment_node_id: str, reason: str) -> None:
        raise NotImplementedError

    def resolve_review_thread(self, thread_node_id: str) -> None:
        raise NotImplementedError


def map_commit(raw: dict[str, Any]) -> Commit:
    return Commit(
        id=raw["id"],
        message=raw["message"],
        author=CommitAuthor(
            name=raw["author_name"],
            email=raw["author_email"],
            date=datetime.datetime.fromisoformat(raw["created_at"]),
        ),
        files=None,
    )
