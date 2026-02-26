from datetime import datetime

import pytest

from sentry.scm.client.scm_rpc_client import SourceCodeManagerRPCClient

# Currently, these tests can only run on my (jacquev6's) computer because they use:
# - my grok endpoint
# - personal repositories and apps I have set up on GitHub and GitLab
# - my Sentry dev server, configured to access these


@pytest.fixture(
    params=(
        params := [
            # https://github.com/jacquev6/test-Sentry-Integration-Dev-jacquev6
            ("GitHub external", ("github", "1159224812")),
            ("GitHub internal", 1),
            # https://gitlab.com/jacquev6-sentry/test-sentry-integration-dev-jacquev6
            ("GitLab external", ("gitlab", "gitlab.com:79787061")),
            ("GitLab internal", 2),
        ]
    ),
    ids=[p[0] for p in params],
)
def client(request: pytest.FixtureRequest) -> SourceCodeManagerRPCClient:
    return SourceCodeManagerRPCClient(
        base_url="http://reprovingly-smartish-jackqueline.ngrok-free.dev",
        shared_secret="yet-another-secret",
        organization_id=1,
        repository_id=request.param[1],
    )


def test_get_commits(client: SourceCodeManagerRPCClient) -> None:
    assert client.get_commits(sha="1403774c82d64068af027d0b5d0cc4f52473b6f2")["data"] == [
        {
            "id": "1403774c82d64068af027d0b5d0cc4f52473b6f2",
            "message": "Initial commit",
            "author": {
                "name": "Vincent Jacques",
                "email": "vincent@vincent-jacques.net",
                "date": datetime.fromisoformat("2026-02-16T14:24:18+01:00"),
            },
            "files": [],
        }
    ]
