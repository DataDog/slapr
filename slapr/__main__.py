import os

import github
import slack

from .config import Config
from .github import GithubClient, WebGithubBackend
from .main import main
from .slack import SlackClient, WebSlackBackend

config = Config(
    slack_client=SlackClient(backend=WebSlackBackend(client=slack.WebClient(os.environ["SLACK_API_TOKEN"]))),
    github_client=GithubClient(backend=WebGithubBackend(gh=github.Github(os.environ["GITHUB_TOKEN"]))),
    slack_channel_id=os.environ["SLACK_CHANNEL_ID"],
    slapr_bot_user_id=os.environ["SLAPR_BOT_USER_ID"],
    emoji_review_started="review_started",
    emoji_approved="approved",
    emoji_needs_change="change_requested",
    emoji_merged="merged",
)

main(config)
