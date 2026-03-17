# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Set

import yaml

if TYPE_CHECKING:
    from .slack import SlackClient
from slack_sdk.errors import SlackApiError


DEFAULT_SLACK_CHANNEL = "DEFAULT_SLACK_CHANNEL"


class ReviewMap:
    def __init__(self, team_to_channel: Dict[str, str], default_channel_id: Optional[str]):
        """
        Args:
            team_to_channel: Mapping of team names to Slack channel IDs.
                             Keys are lowercase, e.g. "@datadog/agent-apm" -> "C01234".
            default_channel_id: Fallback channel ID when no team matches.
        """
        self.team_to_channel = team_to_channel
        self.default_channel_id = default_channel_id

    @staticmethod
    def load(file_path: str, slack_client: "SlackClient", default_channel_id: str) -> "ReviewMap":
        """Load YAML mapping file and resolve channel names to IDs via Slack API.

        YAML format (generic slack map with review and notification channels):
            '@datadog/agent-apm':
              review:
                name: 'apm-review'
                id: 'C01234ABCDE'
              notification:
                name: 'apm-notifications'
                id: 'C09876FGHIJ'
            '@datadog/agent-build':
              review:
                name: 'agent-build'      # id omitted — resolved via Slack API
            '@datadog/agent-ci': 'DEFAULT_SLACK_CHANNEL'

        Only the 'review' subfield is used by ReviewMap. The 'notification'
        subfield is ignored (used by other tools).
        """
        try:
            with open(file_path) as f:
                raw_map = yaml.safe_load(f)
        except yaml.YamlError as e: # Maybe also some OSErrors
            raise ValueError("Invalid YAML data for review map") from e
        if not isinstance(raw_map, dict):
            raise ValueError(f"Invalid YAML data for review map, should be `dict` got `{type(raw_map)}`")

        # First pass: extract channel IDs and collect names that need resolution
        team_to_channel = {}
        teams_pending_resolve = defaultdict(list)  # {channel_name: [team_key, ...]}
        for team, entry in raw_map.items():
            team_key = team.lower()
            if isinstance(entry, str) and entry == DEFAULT_SLACK_CHANNEL:
                team_to_channel[team_key] = default_channel_id
            elif isinstance(entry, dict):
                review_entry = entry.get("review")
                if review_entry is None:
                    print(f"Warning: Entry for {team} has no 'review' subfield, skipping")
                    continue
                if not isinstance(review_entry, dict):
                    print(f"Warning: 'review' for {team} is not a mapping, skipping")
                    continue
                channel_id = review_entry.get("id")
                channel_name = review_entry.get("name")
                if channel_id:
                    team_to_channel[team_key] = channel_id
                elif channel_name:
                    teams_pending_resolve[channel_name].append(team_key)
                else:
                    print(f"Warning: 'review' for {team} has neither 'id' nor 'name', skipping")
            else:
                print(f"Warning: Unexpected format for {team}: {entry!r}, skipping")

        # Resolve channel names to IDs (only for entries without an ID)
        if teams_pending_resolve:
            try:
                name_to_id = slack_client.resolve_channel_names(set(teams_pending_resolve.keys()))
            except SlackApiError as e:
                print(f"Warning: Failed to resolve channel names via Slack API: {e}")
                print("Entries without channel IDs will be skipped. "
                      "Add 'id' field to avoid this.")
                name_to_id = {}

            for channel_name, team_keys in teams_pending_resolve.items():
                if channel_name in name_to_id:
                    for team_key in team_keys:
                        team_to_channel[team_key] = name_to_id[channel_name]
                else:
                    print(f"Warning: Could not resolve channel '{channel_name}' for teams {', '.join(team_keys)}, skipping")

        return ReviewMap(team_to_channel=team_to_channel, default_channel_id=default_channel_id)

    def get_channel_for_teams(self, requested_teams: List[str]) -> List[str]:
        """Given a list of team names (e.g., '@datadog/agent-apm'),
        return the list of matching Slack channel IDs."""
        channels = []
        for team in requested_teams:
            team_key = team.lower()
            if team_key in self.team_to_channel:
                channels.append(self.team_to_channel[team_key])
        return channels

    def get_all_channels(self) -> Set[str]:
        """Return all unique channel IDs in the map."""
        return set(self.team_to_channel.values())
