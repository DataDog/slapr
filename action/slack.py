from typing import Optional, Set

import slack

from . import settings

client = slack.WebClient(token=settings.SLACK_API_TOKEN)


def post_message(channel: str, text: str) -> None:
    response: dict = client.chat_postMessage(channel=channel, text=text)
    assert response["ok"]


def find_timestamp_of_review_requested_message(
    pr_url: str, channel_id: str
) -> Optional[str]:
    response = client.channels_history(channel=channel_id)
    assert response["ok"]

    messages = response["messages"]

    for message in filter(lambda m: m["type"] == "message", messages):
        # TODO: Make less strict.
        if f":eyes: <{pr_url}>" in message.get("text", ""):
            return message["ts"]

    return None


def get_emojis(timestamp: str, channel_id: str) -> Set[str]:
    response = client.reactions_list(channel=channel_id, timestamp=timestamp)
    assert response["ok"]
    return {reaction["name"] for reaction in response["reactions"]}


def add_reaction(timestamp: str, emoji: str, channel_id: str) -> None:
    client.reactions_add(channel=channel_id, name=emoji, timestamp=timestamp)


def remove_reaction(timestamp: str, emoji: str, channel_id: str) -> None:
    client.reactions_remove(channel=channel_id, name=emoji, timestamp=timestamp)
