# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

import re
from typing import Dict, List, NamedTuple, Optional, Set

import slack_sdk
from slack_sdk.errors import SlackApiError

PR_URL_PATTERN = r"<(?P<url>https?://[^>|]+)(?:\|[^>]*)?>"


class SlackChannelAccessError(Exception):
    """Raised when the Slack bot cannot access a channel."""

    def __init__(self, channel_id: str, error: str) -> None:
        self.channel_id = channel_id
        self.error = error
        super().__init__(f"Slack API error '{error}' for channel {channel_id}")


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

    def resolve_channel_names(self, names: Set[str]) -> Dict[str, str]:
        raise NotImplementedError  # pragma: no cover


class WebSlackBackend(SlackBackend):
    def __init__(self, client: slack_sdk.WebClient) -> None:
        self._client = client

    def get_latest_messages(self, channel_id: str) -> List[Message]:
        try:
            response = self._client.conversations_history(channel=channel_id)
        except SlackApiError as e:
            if e.response["error"] == "not_in_channel":
                raise SlackChannelAccessError(channel_id, "not_in_channel") from e
            raise
        if not response["ok"]:
            raise RuntimeError(f"conversations_history failed for channel {channel_id}: {response}")
        return [
            Message(text=message.get("text", ""), timestamp=message["ts"])
            for message in response["messages"]
            if message["type"] == "message"
        ]

    def get_reactions(self, timestamp: str, channel_id: str) -> List[Reaction]:
        try:
            response = self._client.reactions_get(channel=channel_id, timestamp=timestamp)
        except SlackApiError as e:
            if e.response["error"] == "not_in_channel":
                raise SlackChannelAccessError(channel_id, "not_in_channel") from e
            raise
        if not response["ok"]:
            raise RuntimeError(f"reactions_get failed for channel {channel_id}, timestamp {timestamp}: {response}")

        if response["type"] != "message":
            return []

        reactions: List[dict] = response["message"].get("reactions", [])
        return [Reaction(emoji=reaction["name"], user_ids=reaction["users"]) for reaction in reactions]

    def add_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        try:
            self._client.reactions_add(channel=channel_id, name=emoji, timestamp=timestamp)
        except SlackApiError as e:
            if e.response['error'] == 'already_reacted':
                print(f'Warning: Message {timestamp} has already emote {emoji} within channel {channel_id}')
            elif e.response['error'] == 'not_in_channel':
                raise SlackChannelAccessError(channel_id, "not_in_channel") from e
            else:
                print(f'Error: reactions_add failed for channel {channel_id}, emoji {emoji}, timestamp {timestamp}: {e}')
                raise

    def remove_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        try:
            self._client.reactions_remove(channel=channel_id, name=emoji, timestamp=timestamp)
        except SlackApiError as e:
            if e.response['error'] == 'not_in_channel':
                raise SlackChannelAccessError(channel_id, "not_in_channel") from e
            print(f'Error: reactions_remove failed for channel {channel_id}, emoji {emoji}, timestamp {timestamp}: {e}')
            raise

    def resolve_channel_names(self, names: Set[str]) -> Dict[str, str]:
        """Resolve channel names to channel IDs using conversations_list with pagination."""
        remaining = set(names)
        result = {}
        cursor = None
        while remaining:
            kwargs = {"types": "public_channel", "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            response = self._client.conversations_list(**kwargs)
            if not response["ok"]:
                raise RuntimeError(f"conversations_list failed while resolving {names}: {response}")
            for channel in response["channels"]:
                if channel["name"] in remaining:
                    result[channel["name"]] = channel["id"]
                    remaining.discard(channel["name"])
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return result


class SlackClient:
    def __init__(self, *, backend: SlackBackend) -> None:
        self._backend = backend

    def find_timestamp_of_review_requested_message(self, pr_url: str, channel_id: str) -> Optional[str]:
        messages = self._backend.get_latest_messages(channel_id=channel_id)

        for message in messages:
            for match in re.finditer(PR_URL_PATTERN, message.text):
                # Examples:
                # https://github.com/owner/repo/pull/6/files
                # https://github.com/owner/repo/pull/6/s
                url = match.group("url")

                if url.startswith(pr_url):
                    return message.timestamp

        return None

    def get_emojis_for_user(self, timestamp: str, channel_id: str, user_id: str) -> Set[str]:
        reactions = self._backend.get_reactions(timestamp=timestamp, channel_id=channel_id)
        return {reaction.emoji for reaction in reactions if user_id in reaction.user_ids}

    def add_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        self._backend.add_reaction(timestamp=timestamp, emoji=emoji, channel_id=channel_id)

    def remove_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        self._backend.remove_reaction(timestamp=timestamp, emoji=emoji, channel_id=channel_id)

    def resolve_channel_names(self, names: Set[str]) -> Dict[str, str]:
        return self._backend.resolve_channel_names(names)
