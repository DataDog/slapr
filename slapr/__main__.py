import os

import github
import slack

from .config import Config
from .github import GithubClient, WebGithubBackend
from .main import main
from .slack import SlackClient, WebSlackBackend

DEFAULT_TIME_BETWEEN_CALLS = 2000

config = Config(
    slack_client=SlackClient(backend=WebSlackBackend(client=slack.WebClient(os.environ["SLACK_API_TOKEN"]))),
    github_client=GithubClient(
        backend=WebGithubBackend(
            gh=github.Github(os.environ["GITHUB_TOKEN"]),
            event_path=os.environ["GITHUB_EVENT_PATH"],
            repo=os.environ["GITHUB_REPOSITORY"],
        )
    ),
    slack_channel_id=os.environ["SLACK_CHANNEL_ID"],
    slapr_bot_user_id=os.environ["SLAPR_BOT_USER_ID"],
    emoji_review_started=os.environ.get("SLAPR_EMOJI_REVIEW_STARTED", "review_started"),
    emoji_approved=os.environ.get("SLAPR_EMOJI_APPROVED", "approved"),
    emoji_needs_change=os.environ.get("SLAPR_EMOJI_CHANGES_REQUESTED", "changes_requested"),
    emoji_merged=os.environ.get("SLAPR_EMOJI_MERGED", "merged"),
    emoji_closed=os.environ.get("SLAPR_EMOJI_CLOSED", "closed"),
    time_between_calls=os.environ.get("SLAPR_TIME_BETWEEN_CALLS", DEFAULT_TIME_BETWEEN_CALLS),
)

main(config)
