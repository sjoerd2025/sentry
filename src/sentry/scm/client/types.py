from typing import Any, Literal, TypeAlias

import pydantic

ProviderName: TypeAlias = str
ExternalId: TypeAlias = str
RepositoryId: TypeAlias = int | tuple[ProviderName, ExternalId]


Reaction: TypeAlias = Literal["+1", "-1", "laugh", "confused", "heart", "hooray", "rocket", "eyes"]


class Author(pydantic.BaseModel):
    id: str
    username: str


class Comment(pydantic.BaseModel):
    id: str
    body: str | None
    author: Author | None


class CommentActionResult(pydantic.BaseModel):
    comment: Comment
    provider: ProviderName
    raw: dict[str, Any]


class ReactionResult(pydantic.BaseModel):
    id: str
    content: Reaction
    author: Author | None


class PullRequestBranch(pydantic.BaseModel):
    sha: str
    ref: str


class PullRequest(pydantic.BaseModel):
    id: int
    number: int
    title: str
    body: str | None
    state: str
    merged: bool
    url: str
    html_url: str
    head: PullRequestBranch
    base: PullRequestBranch


class PullRequestActionResult(pydantic.BaseModel):
    pull_request: PullRequest
    provider: ProviderName
    raw: dict[str, Any]


class Repository(pydantic.BaseModel):
    integration_id: int
    name: str
    organization_id: int
    status: int


class GitRef(pydantic.BaseModel):
    ref: str
    sha: str


class GitRefActionResult(pydantic.BaseModel):
    git_ref: GitRef
    provider: ProviderName
    raw: dict[str, Any]


class GitBlob(pydantic.BaseModel):
    sha: str


class GitBlobActionResult(pydantic.BaseModel):
    git_blob: GitBlob
    provider: ProviderName
    raw: dict[str, Any]


class FileContent(pydantic.BaseModel):
    path: str
    sha: str
    content: str  # base64-encoded
    encoding: str
    size: int


class FileContentActionResult(pydantic.BaseModel):
    file_content: FileContent
    provider: ProviderName
    raw: dict[str, Any]


class CommitAuthor(pydantic.BaseModel):
    name: str
    email: str
    date: str


class CommitFile(pydantic.BaseModel):
    filename: str
    status: str
    patch: str | None


class Commit(pydantic.BaseModel):
    sha: str
    message: str
    author: CommitAuthor | None
    files: list[CommitFile]


class CommitActionResult(pydantic.BaseModel):
    commit: Commit
    provider: ProviderName
    raw: dict[str, Any]


class CommitComparison(pydantic.BaseModel):
    ahead_by: int
    behind_by: int


class CommitComparisonActionResult(pydantic.BaseModel):
    comparison: CommitComparison
    provider: ProviderName
    raw: dict[str, Any]


class TreeEntry(pydantic.BaseModel):
    path: str
    mode: str
    type: str
    sha: str
    size: int | None


class InputTreeEntry(pydantic.BaseModel):
    path: str
    mode: str
    type: str
    sha: str | None


class GitTree(pydantic.BaseModel):
    tree: list[TreeEntry]
    truncated: bool


class GitTreeActionResult(pydantic.BaseModel):
    git_tree: GitTree
    provider: ProviderName
    raw: dict[str, Any]


class GitCommitTree(pydantic.BaseModel):
    sha: str


class GitCommitObject(pydantic.BaseModel):
    sha: str
    tree: GitCommitTree
    message: str


class GitCommitObjectActionResult(pydantic.BaseModel):
    git_commit: GitCommitObject
    provider: ProviderName
    raw: dict[str, Any]


class PullRequestFile(pydantic.BaseModel):
    filename: str
    status: str
    patch: str | None
    changes: int
    sha: str
    previous_filename: str | None


class PullRequestFileActionResult(pydantic.BaseModel):
    files: list[PullRequestFile]
    provider: ProviderName
    raw: list[dict[str, Any]]


class PullRequestCommit(pydantic.BaseModel):
    sha: str
    message: str
    author: CommitAuthor | None


class PullRequestCommitActionResult(pydantic.BaseModel):
    commits: list[PullRequestCommit]
    provider: ProviderName
    raw: list[dict[str, Any]]


class PullRequestDiffActionResult(pydantic.BaseModel):
    diff: str
    provider: ProviderName


class ReviewCommentInput(pydantic.BaseModel):
    path: str
    body: str
    line: int | None = None
    side: str | None = None
    start_line: int | None = None
    start_side: str | None = None


class ReviewComment(pydantic.BaseModel):
    id: int
    html_url: str
    path: str
    body: str


class ReviewCommentActionResult(pydantic.BaseModel):
    review_comment: ReviewComment
    provider: ProviderName
    raw: dict[str, Any]


class Review(pydantic.BaseModel):
    id: int
    html_url: str


class ReviewActionResult(pydantic.BaseModel):
    review: Review
    provider: ProviderName
    raw: dict[str, Any]


class CheckRunOutput(pydantic.BaseModel):
    title: str
    summary: str
    text: str | None = None


class CheckRun(pydantic.BaseModel):
    id: int
    name: str
    status: str
    conclusion: str | None
    html_url: str


class CheckRunActionResult(pydantic.BaseModel):
    check_run: CheckRun
    provider: ProviderName
    raw: dict[str, Any]
