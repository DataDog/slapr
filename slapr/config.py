from typing import NamedTuple

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
