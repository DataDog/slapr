# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Set

import re
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
        except yaml.YAMLError as e:
            raise ValueError("Invalid YAML data for review map") from e
        if not isinstance(raw_map, dict):
            raise ValueError(f"Invalid YAML data for review map, should be `dict` got `{type(raw_map)}`")

        # First pass: extract channel IDs and collect names that need resolution
        team_to_channel = {}
        teams_pending_resolve = defaultdict(list)  # {channel_name: [team_key, ...]}
        team_format = re.compile(r"\@[a-zA-Z0-9-_]+\/[a-zA-Z0-9-_]+")
        for team, entry in raw_map.items():
            team_key = team.lower()
            if not team_format.match(team):
                print(f"Warning: Team {team_key} is not a valid @organization/team-slug format, skipping")
                continue
            match entry:
                case str() if entry == DEFAULT_SLACK_CHANNEL:
                    team_to_channel[team_key] = default_channel_id
                case {"review": {"id": str(channel_id), **_rest}}:
                    team_to_channel[team_key] = channel_id
                case {"review": {"name": str(channel_name), **_rest}}:
                    teams_pending_resolve[channel_name].append(team_key)
                case {"review": dict()}:
                    print(f"Warning: 'review' for {team} has neither 'id' nor 'name', skipping")
                case {"review": _}:
                    print(f"Warning: 'review' for {team} is not a mapping, skipping")
                case dict():
                    print(f"Warning: Entry for {team} has no 'review' subfield, skipping")
                case _:
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

    def get_channels_for_requested_teams(self, requested_teams: List) -> Set[str]:
        """Return all Slack channel IDs for the given requested teams.

        Each team is expected to have .organization.login and .slug attributes
        (PyGithub Team objects). Teams not in the map fall back to default_channel_id.
        """
        channels = set()
        for team in requested_teams:
            full_team = f"@{team.organization.login}/{team.slug}".lower()
            channels.add(self.team_to_channel.get(full_team, self.default_channel_id))
        return channels
