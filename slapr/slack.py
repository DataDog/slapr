import re
from typing import List, Optional, Set

import slack

from . import settings

client = slack.WebClient(token=settings.SLACK_API_TOKEN)


def post_message(channel: str, text: str) -> None:
    response: dict = client.chat_postMessage(channel=channel, text=text)
    assert response["ok"]


def find_timestamp_of_review_requested_message(pr_url: str, channel_id: str) -> Optional[str]:
    response = client.channels_history(channel=channel_id)
    assert response["ok"]

    messages = response["messages"]

    for message in filter(lambda m: m["type"] == "message", messages):
        text = message.get("text", "")
        match = re.search(settings.SLAPR_SEARCH_PATTERN, text)

        if match is None:
            continue

        # Examples:
        # https://github.com/owner/repo/pull/6/files
        # https://github.com/owner/repo/pull/6/s
        url = match.group("url")

        if not url.startswith(pr_url):
            continue

        return message["ts"]

    return None


def get_emojis(timestamp: str, channel_id: str) -> Set[str]:
    response = client.reactions_get(channel=channel_id, timestamp=timestamp)
    assert response["ok"]

    if response["type"] != "message":
        return set()

    reactions: List[dict] = response["message"].get("reactions", [])

    return {reaction["name"] for reaction in reactions if settings.SLAPR_BOT_USER_ID in reaction["users"]}


def add_reaction(timestamp: str, emoji: str, channel_id: str) -> None:
    client.reactions_add(channel=channel_id, name=emoji, timestamp=timestamp)


def remove_reaction(timestamp: str, emoji: str, channel_id: str) -> None:
    client.reactions_remove(channel=channel_id, name=emoji, timestamp=timestamp)
