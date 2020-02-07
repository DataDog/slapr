import os

GITHUB_EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO = os.environ["GITHUB_REPO"]

SLACK_API_TOKEN = os.environ["SLACK_API_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]

SLAPR_BOT_USER_ID = os.environ["SLAPR_BOT_USER_ID"]

SLAPR_SEARCH_PATTERN = r'(:eyes:|rev)\s*<[^<>]*>'

EMOJI_REVIEW_STARTED = "review_started"
EMOJI_READY_TO_MERGE = "approved"
EMOJI_NEEDS_CHANGES = "change_requested"
EMOJI_MERGED = "merged"
