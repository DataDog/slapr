# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

import os
import tempfile

import pytest

from slapr.review_map import DEFAULT_SLACK_CHANNEL, ReviewMap
from slapr.slack import SlackBackend, SlackClient


class MockSlackBackendForResolve(SlackBackend):
    def __init__(self, channel_map):
        self._channel_map = channel_map  # {"channel-name": "C_ID"}

    def resolve_channel_names(self, names):
        return {name: self._channel_map[name] for name in names if name in self._channel_map}


def _make_slack_client(channel_map):
    return SlackClient(backend=MockSlackBackendForResolve(channel_map))


def test_load_basic():
    yaml_content = """
'@datadog/agent-apm': '#apm-agent'
'@datadog/agent-build': '#agent-build'
"""
    slack_client = _make_slack_client({"apm-agent": "C_APM", "agent-build": "C_BUILD"})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {
        "@datadog/agent-apm": "C_APM",
        "@datadog/agent-build": "C_BUILD",
    }
    assert review_map.default_channel_id == "C_DEFAULT"


def test_load_with_default_channel():
    yaml_content = """
'@datadog/agent-apm': '#apm-agent'
'@datadog/agent-ci': 'DEFAULT_SLACK_CHANNEL'
"""
    slack_client = _make_slack_client({"apm-agent": "C_APM"})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {
        "@datadog/agent-apm": "C_APM",
        "@datadog/agent-ci": "C_DEFAULT",
    }


def test_load_with_raw_channel_id():
    yaml_content = """
'@datadog/agent-apm': 'C_ALREADY_AN_ID'
"""
    slack_client = _make_slack_client({})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {"@datadog/agent-apm": "C_ALREADY_AN_ID"}


def test_load_unresolvable_channel(capsys):
    yaml_content = """
'@datadog/agent-apm': '#nonexistent-channel'
"""
    slack_client = _make_slack_client({})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {}
    assert "Could not resolve" in capsys.readouterr().out


def test_load_empty_file():
    yaml_content = ""
    slack_client = _make_slack_client({})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {}
    assert review_map.default_channel_id == "C_DEFAULT"


def test_get_channel_for_teams():
    review_map = ReviewMap(
        team_to_channel={
            "@datadog/agent-apm": "C_APM",
            "@datadog/agent-build": "C_BUILD",
        },
        default_channel_id="C_DEFAULT",
    )

    assert review_map.get_channel_for_teams(["@datadog/agent-apm"]) == ["C_APM"]
    assert review_map.get_channel_for_teams(["@datadog/agent-apm", "@datadog/agent-build"]) == ["C_APM", "C_BUILD"]
    assert review_map.get_channel_for_teams(["@datadog/unknown-team"]) == []
    assert review_map.get_channel_for_teams([]) == []


def test_get_channel_for_teams_case_insensitive():
    review_map = ReviewMap(
        team_to_channel={"@datadog/agent-apm": "C_APM"},
        default_channel_id="C_DEFAULT",
    )
    assert review_map.get_channel_for_teams(["@Datadog/Agent-APM"]) == ["C_APM"]


def test_get_all_channels():
    review_map = ReviewMap(
        team_to_channel={
            "@datadog/agent-apm": "C_APM",
            "@datadog/agent-build": "C_BUILD",
            "@datadog/agent-ci": "C_APM",  # duplicate channel
        },
        default_channel_id="C_DEFAULT",
    )

    assert review_map.get_all_channels() == {"C_APM", "C_BUILD"}


def test_load_with_inline_channel_ids():
    """When channel IDs are provided inline (#name:ID), no API resolution is needed."""
    yaml_content = """
'@datadog/agent-apm': '#apm-agent:C_APM'
'@datadog/agent-build': '#agent-build:C_BUILD'
"""
    # Empty channel map — resolve should not be called for these entries
    slack_client = _make_slack_client({})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {
        "@datadog/agent-apm": "C_APM",
        "@datadog/agent-build": "C_BUILD",
    }


def test_load_mixed_inline_and_resolve():
    """Mix of inline IDs and names that need resolution."""
    yaml_content = """
'@datadog/agent-apm': '#apm-agent:C_APM'
'@datadog/agent-build': '#agent-build'
'@datadog/agent-ci': 'DEFAULT_SLACK_CHANNEL'
"""
    slack_client = _make_slack_client({"agent-build": "C_BUILD"})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {
        "@datadog/agent-apm": "C_APM",
        "@datadog/agent-build": "C_BUILD",
        "@datadog/agent-ci": "C_DEFAULT",
    }
