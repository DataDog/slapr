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
from .review_map import ReviewMap
from .slack import SlackClient, WebSlackBackend

slack_backend = WebSlackBackend(client=slack_sdk.WebClient(os.environ["SLACK_API_TOKEN"]))
slack_client = SlackClient(backend=slack_backend)

review_map = None
review_map_path = os.environ.get("SLAPR_REVIEW_MAP")
if review_map_path:
    review_map = ReviewMap.load(
        file_path=review_map_path,
        slack_client=slack_client,
        default_channel_id=os.environ["SLACK_CHANNEL_ID"],
    )

config = Config(
    slack_client=slack_client,
    github_client=GithubClient(
        backend=WebGithubBackend(
            gh=github.Github(os.environ["GITHUB_TOKEN"]),
            event_path=os.environ["GITHUB_EVENT_PATH"],
            repo=os.environ["GITHUB_REPOSITORY"],
        )
    ),
    slack_channel_id=os.environ["SLACK_CHANNEL_ID"],
    slapr_bot_user_id=os.environ["SLAPR_BOT_USER_ID"],
    number_of_approvals_required=max(1, int(os.environ.get("SLAPR_NUMBER_OF_APPROVALS_REQUIRED", 1))),
    emoji_review_started=os.environ.get("SLAPR_EMOJI_REVIEW_STARTED", "review_started"),
    emoji_approved=os.environ.get("SLAPR_EMOJI_APPROVED", "approved"),
    emoji_approved_with_comments=os.environ.get("SLAPR_EMOJI_APPROVED_WITH_COMMENTS", "approved_with_comments"),
    emoji_needs_change=os.environ.get("SLAPR_EMOJI_CHANGES_REQUESTED", "changes_requested"),
    emoji_merged=os.environ.get("SLAPR_EMOJI_MERGED", "merged"),
    emoji_closed=os.environ.get("SLAPR_EMOJI_CLOSED", "closed"),
    emoji_commented=os.environ.get("SLAPR_EMOJI_COMMENTED", "comment"),
    review_map=review_map,
)

main(config)
