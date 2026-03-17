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


def test_load_with_review_name_and_id():
    """When review has both name and id, id is used directly (no API call)."""
    yaml_content = """
'@datadog/agent-apm':
  review:
    name: 'apm-review'
    id: 'C_APM'
'@datadog/agent-build':
  review:
    name: 'agent-build-review'
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


def test_load_review_name_only_resolves_via_api():
    """When review has only name, channel is resolved via Slack API."""
    yaml_content = """
'@datadog/agent-apm':
  review:
    name: 'apm-review'
'@datadog/agent-build':
  review:
    name: 'agent-build-review'
"""
    slack_client = _make_slack_client({"apm-review": "C_APM", "agent-build-review": "C_BUILD"})

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
  review:
    name: 'apm-review'
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
  review:
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
        with pytest.raises(ValueError, match="Invalid YAML data for review map"):
            ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)



def test_get_channels_for_requested_teams():
    review_map = ReviewMap(
        team_to_channel={
            "@datadog/agent-apm": "C_APM",
            "@datadog/agent-build": "C_BUILD",
        },
        default_channel_id="C_DEFAULT",
    )

    class FakeOrg:
        login = "datadog"

    class FakeTeam:
        def __init__(self, slug):
            self.slug = slug
            self.organization = FakeOrg()

    assert review_map.get_channels_for_requested_teams([FakeTeam("agent-apm")]) == {"C_APM"}
    assert review_map.get_channels_for_requested_teams([FakeTeam("agent-apm"), FakeTeam("agent-build")]) == {"C_APM", "C_BUILD"}
    assert review_map.get_channels_for_requested_teams([FakeTeam("unknown-team")]) == {"C_DEFAULT"}
    assert review_map.get_channels_for_requested_teams([]) == set()


def test_load_mixed_id_and_resolve():
    """Mix of entries with id and entries needing resolution."""
    yaml_content = """
'@datadog/agent-apm':
  review:
    name: 'apm-review'
    id: 'C_APM'
'@datadog/agent-build':
  review:
    name: 'agent-build-review'
'@datadog/agent-ci': 'DEFAULT_SLACK_CHANNEL'
"""
    slack_client = _make_slack_client({"agent-build-review": "C_BUILD"})

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


def test_load_no_review_subfield(capsys):
    """Entry with notification but no review subfield should be skipped."""
    yaml_content = """
'@datadog/agent-apm':
  notification:
    name: 'apm-notif'
    id: 'C_NOTIF'
"""
    slack_client = _make_slack_client({})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {}
    assert "no 'review' subfield" in capsys.readouterr().out


def test_load_notification_ignored():
    """The notification subfield should be ignored, only review is used."""
    yaml_content = """
'@datadog/agent-apm':
  notification:
    name: 'apm-notif'
    id: 'C_NOTIF'
  review:
    name: 'apm-review'
    id: 'C_REVIEW'
"""
    slack_client = _make_slack_client({})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        review_map = ReviewMap.load(f.name, slack_client, default_channel_id="C_DEFAULT")

    os.unlink(f.name)

    assert review_map.team_to_channel == {"@datadog/agent-apm": "C_REVIEW"}


def test_load_multiple_teams_same_channel_name():
    """Multiple teams sharing the same review channel name should all map correctly."""
    yaml_content = """
'@datadog/agent-apm':
  review:
    name: 'shared-channel'
'@datadog/agent-build':
  review:
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
