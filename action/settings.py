import os

GITHUB_EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]

# TODO: Make these configurable.
SLACK_STATE_TO_EMOJI = {
    "commented": "speech_balloon",
    "approved": "white_check_mark",
    "changes_requested": "pencil2",
}

SLACK_API_TOKEN = os.environ["SLACK_API_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
