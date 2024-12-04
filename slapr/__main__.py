# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

import os

import github
import slack_sdk

from .config import Config
from .github import GithubClient, WebGithubBackend
from .main import main
from .slack import SlackClient, WebSlackBackend


config = Config(
    slack_client=SlackClient(backend=WebSlackBackend(client=slack_sdk.WebClient(os.environ["SLACK_API_TOKEN"]))),
    github_client=GithubClient(
        backend=WebGithubBackend(
            gh=github.Github(os.environ["GITHUB_TOKEN"]),
            event_path=os.environ["GITHUB_EVENT_PATH"],
            repo=os.environ["GITHUB_REPOSITORY"],
        )
    ),
    slack_channel_id=os.environ.get("SLACK_CHANNEL_ID"),
    slapr_multichannel=os.environ.get("SLAPR_MULTICHANNEL", "false").lower() == "true",
    slapr_multichannel_team_mapping=os.environ.get("SLAPR_MULTICHANNEL_TEAM_MAPPING"),
    slapr_multichannel_org=os.environ.get("SLAPR_MULTICHANNEL_ORG", os.environ["GITHUB_REPOSITORY"].split("/")[0]),
    slapr_bot_user_id=os.environ["SLAPR_BOT_USER_ID"],
    number_of_approvals_required=max(1, int(os.environ.get("SLAPR_NUMBER_OF_APPROVALS_REQUIRED", 1))),
    emoji_review_started=os.environ.get("SLAPR_EMOJI_REVIEW_STARTED", "review_started"),
    emoji_approved=os.environ.get("SLAPR_EMOJI_APPROVED", "approved"),
    emoji_needs_change=os.environ.get("SLAPR_EMOJI_CHANGES_REQUESTED", "changes_requested"),
    emoji_merged=os.environ.get("SLAPR_EMOJI_MERGED", "merged"),
    emoji_closed=os.environ.get("SLAPR_EMOJI_CLOSED", "closed"),
    emoji_commented=os.environ.get("SLAPR_EMOJI_COMMENTED", "comment"),
)
config.verify()

main(config)
