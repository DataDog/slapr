from typing import Callable, NamedTuple

from .github import GithubClient
from .slack import SlackClient


class Config(NamedTuple):
    slack_client: SlackClient
    github_client: GithubClient

    slack_channel_id: str
    slapr_bot_user_id: str  # TODO: document how to obtain this user ID, or automate its retrieval.

    emoji_review_started: str
    emoji_approved: str
    emoji_needs_change: str
    emoji_merged: str
    emoji_closed: str

    time_between_calls: int  # in milliseconds

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
