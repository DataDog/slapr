import re
from typing import List, NamedTuple, Optional, Set

import slack

PR_URL_PATTERN = r"<(?P<url>.*)>"


class Message(NamedTuple):
    text: str
    timestamp: str


class Reaction(NamedTuple):
    emoji: str
    user_ids: List[str]


class SlackBackend:
    def get_latest_messages(self, channel_id: str) -> List[Message]:
        raise NotImplementedError  # pragma: no cover

    def get_reactions(self, timestamp: str, channel_id: str) -> List[Reaction]:
        raise NotImplementedError  # pragma: no cover

    def add_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        raise NotImplementedError  # pragma: no cover

    def remove_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        raise NotImplementedError  # pragma: no cover


class WebSlackBackend(SlackBackend):
    def __init__(self, client: slack.WebClient) -> None:
        self._client = client

    def get_latest_messages(self, channel_id: str) -> List[Message]:
        response = self._client.conversations_history(channel=channel_id)
        assert response["ok"]
        return [
            Message(text=message.get("text", ""), timestamp=message["ts"])
            for message in response["messages"]
            if message["type"] == "message"
        ]

    def get_reactions(self, timestamp: str, channel_id: str) -> List[Reaction]:
        response = self._client.reactions_get(channel=channel_id, timestamp=timestamp)
        assert response["ok"]

        if response["type"] != "message":
            return []

        reactions: List[dict] = response["message"].get("reactions", [])
        return [Reaction(emoji=reaction["name"], user_ids=reaction["users"]) for reaction in reactions]

    def add_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        self._client.reactions_add(channel=channel_id, name=emoji, timestamp=timestamp)

    def remove_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        self._client.reactions_remove(channel=channel_id, name=emoji, timestamp=timestamp)


class SlackClient:
    def __init__(self, *, backend: SlackBackend) -> None:
        self._backend = backend

    def find_timestamp_of_review_requested_message(self, pr_url: str, channel_id: str) -> Optional[str]:
        messages = self._backend.get_latest_messages(channel_id=channel_id)

        for message in messages:
            match = re.search(PR_URL_PATTERN, message.text)

            if match is None:
                continue

            # Examples:
            # https://github.com/owner/repo/pull/6/files
            # https://github.com/owner/repo/pull/6/s
            url = match.group("url")

            if not url.startswith(pr_url):
                continue

            return message.timestamp

        return None

    def get_emojis_for_user(self, timestamp: str, channel_id: str, user_id: str) -> Set[str]:
        reactions = self._backend.get_reactions(timestamp=timestamp, channel_id=channel_id)
        return {reaction.emoji for reaction in reactions if user_id in reaction.user_ids}

    def add_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        self._backend.add_reaction(timestamp=timestamp, emoji=emoji, channel_id=channel_id)

    def remove_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        self._backend.remove_reaction(timestamp=timestamp, emoji=emoji, channel_id=channel_id)
