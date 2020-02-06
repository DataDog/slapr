from typing import Optional

import slack

from . import settings

client = slack.WebClient(token=settings.SLACK_API_TOKEN)


def post_message(channel: str, text: str) -> None:
    response: dict = client.chat_postMessage(channel=channel, text=text)
    assert response["ok"]


def find_timestamp_of_review_requested_message(
    pr_url: str, channel_id: str
) -> Optional[str]:
    """
    Find the timestamp of Slack message where the author
    requested a review for the given PR.
    """
    response = client.channels_history(channel=channel_id)
    assert response["ok"]

    messages = response["messages"]

    for message in filter(lambda m: m["type"] == "message", messages):
        if f":eyes: <{pr_url}>" in message.get("text", ""):
            return message["ts"]

    return None


def add_reaction(timestamp: str, emoji: str, channel_id: str) -> None:
    """
    Add a reaction to a Slack message.

    See: https://api.slack.com/methods/reactions.add
    """
    client.reactions_add(channel=channel_id, name=emoji, timestamp=timestamp)


def get_emoji_for_state(state: str) -> Optional[str]:
    return settings.SLACK_STATE_TO_EMOJI.get(state)
