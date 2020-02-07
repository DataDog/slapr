from typing import NamedTuple

from .github import GithubClient
from .slack import SlackClient


class Config(NamedTuple):
    slack_client: SlackClient
    github_client: GithubClient

    slack_channel_id: str
    slapr_bot_user_id: str

    emoji_review_started: str = "review_started"
    emoji_approved: str = "approved"
    emoji_needs_change: str = "needs_change"
    emoji_merged: str = "merged"
    emoji_closed: str = "closed"
