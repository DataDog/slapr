# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import Dict, List, Optional, Set

import yaml


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
    def load(file_path: str, slack_client, default_channel_id: str) -> "ReviewMap":
        """Load YAML mapping file and resolve channel names to IDs via Slack API.

        YAML format:
            '@datadog/agent-apm': '#apm-agent'
            '@datadog/agent-build': '#agent-build'
            '@datadog/agent-ci': 'DEFAULT_SLACK_CHANNEL'
        """
        with open(file_path) as f:
            raw_map = yaml.safe_load(f)

        if not raw_map:
            return ReviewMap(team_to_channel={}, default_channel_id=default_channel_id)

        # Collect channel names that need resolution (strip '#' prefix)
        channel_names = set()
        for channel_ref in raw_map.values():
            if channel_ref != DEFAULT_SLACK_CHANNEL and channel_ref.startswith("#"):
                channel_names.add(channel_ref.lstrip("#"))

        # Resolve channel names to IDs
        name_to_id = {}
        if channel_names:
            name_to_id = slack_client.resolve_channel_names(channel_names)

        # Build the resolved map
        team_to_channel = {}
        for team, channel_ref in raw_map.items():
            team_key = team.lower()
            if channel_ref == DEFAULT_SLACK_CHANNEL:
                team_to_channel[team_key] = default_channel_id
            elif channel_ref.startswith("#"):
                channel_name = channel_ref.lstrip("#")
                if channel_name in name_to_id:
                    team_to_channel[team_key] = name_to_id[channel_name]
                else:
                    print(f"Warning: Could not resolve channel {channel_ref} for team {team}, skipping")
            else:
                # Assume it's already a channel ID
                team_to_channel[team_key] = channel_ref

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
