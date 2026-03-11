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
    def _parse_channel_ref(channel_ref: str):
        """Parse a channel reference value from the YAML map.

        Supported formats:
            '#channel-name:C01234ABCDE'  -> (channel_id='C01234ABCDE', needs_resolve=False)
            '#channel-name'              -> (channel_name='channel-name', needs_resolve=True)
            'C01234ABCDE'                -> (channel_id='C01234ABCDE', needs_resolve=False)
            'DEFAULT_SLACK_CHANNEL'      -> (sentinel, needs_resolve=False)
        """
        if channel_ref == DEFAULT_SLACK_CHANNEL:
            return DEFAULT_SLACK_CHANNEL, False
        if channel_ref.startswith("#") and ":" in channel_ref:
            # Format: '#channel-name:C01234ABCDE'
            channel_id = channel_ref.split(":", 1)[1]
            return channel_id, False
        if channel_ref.startswith("#"):
            # Format: '#channel-name' — needs API resolution
            return channel_ref.lstrip("#"), True
        # Raw channel ID
        return channel_ref, False

    @staticmethod
    def load(file_path: str, slack_client, default_channel_id: str) -> "ReviewMap":
        """Load YAML mapping file and resolve channel names to IDs via Slack API.

        YAML format:
            '@datadog/agent-apm': '#apm-agent:C01234ABCDE'   # channel name + ID (preferred)
            '@datadog/agent-build': '#agent-build'             # resolved via Slack API
            '@datadog/agent-ci': 'DEFAULT_SLACK_CHANNEL'
            '@datadog/agent-platform': 'C09876FGHIJ'           # raw channel ID
        """
        with open(file_path) as f:
            raw_map = yaml.safe_load(f)

        if not raw_map:
            return ReviewMap(team_to_channel={}, default_channel_id=default_channel_id)

        # First pass: parse all refs, collect names that need resolution
        parsed = {}
        names_to_resolve = set()
        for team, channel_ref in raw_map.items():
            value, needs_resolve = ReviewMap._parse_channel_ref(channel_ref)
            parsed[team] = (value, needs_resolve)
            if needs_resolve:
                names_to_resolve.add(value)

        # Resolve channel names to IDs (only for entries without an inline ID)
        name_to_id = {}
        if names_to_resolve:
            name_to_id = slack_client.resolve_channel_names(names_to_resolve)

        # Build the resolved map
        team_to_channel = {}
        for team, (value, needs_resolve) in parsed.items():
            team_key = team.lower()
            if value == DEFAULT_SLACK_CHANNEL:
                team_to_channel[team_key] = default_channel_id
            elif needs_resolve:
                if value in name_to_id:
                    team_to_channel[team_key] = name_to_id[value]
                else:
                    print(f"Warning: Could not resolve channel #{value} for team {team}, skipping")
            else:
                team_to_channel[team_key] = value

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
