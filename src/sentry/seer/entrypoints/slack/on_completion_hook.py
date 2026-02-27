from __future__ import annotations

import logging

from sentry.models.organization import Organization
from sentry.seer.entrypoints.cache import SeerOperatorExplorerCache
from sentry.seer.entrypoints.slack.entrypoint import (
    SlackEntrypoint,
    SlackExplorerCachePayload,
)
from sentry.seer.entrypoints.types import SeerEntrypointKey
from sentry.seer.explorer.on_completion_hook import ExplorerOnCompletionHook

logger = logging.getLogger(__name__)


class SlackExplorerCompletionHook(ExplorerOnCompletionHook):
    """Called when an Explorer run triggered via Slack @mention completes."""

    @classmethod
    def execute(cls, organization: Organization, run_id: int) -> None:
        cache_payload = SeerOperatorExplorerCache[SlackExplorerCachePayload].get(
            entrypoint_key=SeerEntrypointKey.SLACK,
            run_id=run_id,
        )
        if not cache_payload:
            logger.info(
                "seer.entrypoint.slack.explorer_completion_hook.cache_miss",
                extra={"run_id": run_id, "organization_id": organization.id},
            )
            return

        SlackEntrypoint.on_explorer_update(cache_payload)
