# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import Callable, NamedTuple

from .github import GithubClient
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

    @property
    def emojis_by_review_step(self) -> Callable[[str], int]:
        """A key function for sorting emojis in the order of the usual review process.

        Suitable for usage with `sorted(...key=...)` or `some_list.sort(key=...)`.
        """
        review_steps_as_emojis = [
            self.emoji_review_started,
            self.emoji_needs_change,
            self.emoji_approved,
            self.emoji_closed,
            self.emoji_merged,
        ]

        return lambda emoji: review_steps_as_emojis.index(emoji)
