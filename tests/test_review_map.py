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


def test_load_with_name_and_id():
    """When both name and id are provided, id is used directly (no API call)."""
    yaml_content = """
'@datadog/agent-apm':
  name: 'apm-agent'
  id: 'C_APM'
'@datadog/agent-build':
  name: 'agent-build'
  id: 'C_BUILD'
"""
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
    assert review_map.default_channel_id == "C_DEFAULT"


def test_load_name_only_resolves_via_api():
    """When only name is provided, channel is resolved via Slack API."""
    yaml_content = """
'@datadog/agent-apm':
  name: 'apm-agent'
'@datadog/agent-build':
  name: 'agent-build'
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


def test_load_with_default_channel():
    yaml_content = """
'@datadog/agent-apm':
  name: 'apm-agent'
  id: 'C_APM'
'@datadog/agent-ci': 'DEFAULT_SLACK_CHANNEL'
"""
    slack_client = _make_slack_client({})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {
        "@datadog/agent-apm": "C_APM",
        "@datadog/agent-ci": "C_DEFAULT",
    }


def test_load_unresolvable_channel(capsys):
    yaml_content = """
'@datadog/agent-apm':
  name: 'nonexistent-channel'
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


def test_load_mixed_id_and_resolve():
    """Mix of entries with id and entries needing resolution."""
    yaml_content = """
'@datadog/agent-apm':
  name: 'apm-agent'
  id: 'C_APM'
'@datadog/agent-build':
  name: 'agent-build'
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


def test_load_missing_name_and_id(capsys):
    """Entry with neither name nor id should be skipped with a warning."""
    yaml_content = """
'@datadog/agent-apm':
  foo: 'bar'
"""
    slack_client = _make_slack_client({})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {}
    assert "neither" in capsys.readouterr().out.lower()


def test_load_multiple_teams_same_channel_name():
    """Multiple teams sharing the same channel name (resolved via API) should all map correctly."""
    yaml_content = """
'@datadog/agent-apm':
  name: 'shared-channel'
'@datadog/agent-build':
  name: 'shared-channel'
"""
    slack_client = _make_slack_client({"shared-channel": "C_SHARED"})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {
        "@datadog/agent-apm": "C_SHARED",
        "@datadog/agent-build": "C_SHARED",
    }
