# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import Callable, Dict, FrozenSet, NamedTuple, Optional, Set

from . import statuses
from .github import GithubClient
from .review_map import ReviewMap
from .slack import SlackClient


class Config(NamedTuple):
    slack_client: SlackClient
    github_client: GithubClient

    slack_channel_id: str
    slapr_bot_user_id: str  # TODO: document how to obtain this user ID, or automate its retrieval.

    number_of_approvals_required: int

    emoji_review_started: str
    emoji_approved: str
    emoji_needs_change: str
    emoji_merged: str
    emoji_closed: str
    emoji_commented: str

    emoji_partially_approved: Optional[str] = None
    review_map: Optional[ReviewMap] = None
    disabled_statuses: FrozenSet[str] = frozenset()

    @property
    def emoji_by_status(self) -> Dict[str, Optional[str]]:
        """Configured emoji for each status (see `slapr.statuses`), in the order of the usual review process."""
        return {
            statuses.REVIEW_STARTED: self.emoji_review_started,
            statuses.COMMENTED: self.emoji_commented,
            statuses.CHANGES_REQUESTED: self.emoji_needs_change,
            statuses.PARTIALLY_APPROVED: self.emoji_partially_approved,
            statuses.APPROVED: self.emoji_approved,
            statuses.CLOSED: self.emoji_closed,
            statuses.MERGED: self.emoji_merged,
        }

    @property
    def emojis_by_review_step(self) -> Callable[[str], int]:
        """A key function for sorting emojis in the order of the usual review process.

        Suitable for usage with `sorted(...key=...)` or `some_list.sort(key=...)`.
        """
        review_steps_as_emojis = [emoji for emoji in self.emoji_by_status.values() if emoji is not None]

        return lambda emoji: review_steps_as_emojis.index(emoji)

    @property
    def disabled_emojis(self) -> Set[str]:
        """Emojis that must never be shown, derived from `disabled_statuses`."""
        emoji_by_status = self.emoji_by_status
        disabled: Set[str] = set()
        for status in self.disabled_statuses:
            emoji = emoji_by_status[status]
            if emoji is not None:
                disabled.add(emoji)
        return disabled
