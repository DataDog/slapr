# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import Dict, List, Optional, Set

import pytest

import slapr
from slapr.config import Config
from slapr.github import GithubBackend, GithubClient, PullRequest, Review
from slapr.review_map import ReviewMap
from slapr.slack import Message, Reaction, SlackBackend, SlackClient


class MockSlackBackend(SlackBackend):
    def __init__(
        self,
        messages: List[Message],
        target_message: Message,
        reactions: List[Reaction],
        channel_messages: Optional[Dict[str, List[Message]]] = None,
        channel_reactions: Optional[Dict[str, List[Reaction]]] = None,
    ) -> None:
        self.messages = messages
        self.target_message = target_message
        self.reactions = reactions
        self.emojis = [reaction.emoji for reaction in reactions]  # Retain order.
        # Multi-channel support: per-channel messages and emoji tracking
        self.channel_messages = channel_messages or {}
        self.channel_emojis: Dict[str, List[str]] = {}
        self._channel_reactions: Dict[str, List[Reaction]] = channel_reactions or {}
        if channel_reactions:
            for ch_id, ch_reactions in channel_reactions.items():
                self.channel_emojis[ch_id] = [r.emoji for r in ch_reactions]

    def get_latest_messages(self, channel_id: str) -> List[Message]:
        if channel_id in self.channel_messages:
            return self.channel_messages[channel_id]
        return self.messages

    def get_reactions(self, timestamp: str, channel_id: str) -> List[Reaction]:
        if channel_id in self._channel_reactions:
            return list(self._channel_reactions[channel_id])
        return list(self.reactions)

    def add_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        if channel_id in self.channel_emojis:
            emojis_list = self.channel_emojis[channel_id]
            if emoji in emojis_list:
                raise RuntimeError(f"Emoji already present: {emoji!r}")
            emojis_list.append(emoji)
        else:
            if emoji in self.emojis:
                raise RuntimeError(f"Emoji already present: {emoji!r}")  # Mimick behavior of real Slack.
            self.emojis.append(emoji)

    def remove_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        if channel_id in self.channel_emojis:
            emojis_list = self.channel_emojis[channel_id]
            if emoji in emojis_list:
                emojis_list.remove(emoji)
        else:
            if emoji not in self.emojis:
                return  # Mimick behavior of real Slack.
            self.emojis.remove(emoji)

    def resolve_channel_names(self, names: Set[str]) -> Dict[str, str]:
        return {}


class MockGithubBackend(GithubBackend):
    def __init__(
        self,
        reviews: List[Review],
        event: dict,
        pr: PullRequest,
        team_members: Optional[Dict[str, List[str]]] = None,
        requested_teams_timeline: Optional[List[str]] = None,
    ) -> None:
        self.reviews = reviews
        self.event = event
        self.pr = pr
        # team_members: {"team-slug": ["user1", "user2"]}
        self.team_members = team_members or {}
        # requested_teams_timeline: list of team slugs from timeline API
        self.requested_teams_timeline = requested_teams_timeline or []

    def read_event(self) -> dict:
        return self.event

    def get_pr(self, pr_number: int) -> PullRequest:
        assert pr_number == self.event["pull_request"]["number"]
        return self.pr

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        assert pr_number == self.event["pull_request"]["number"]
        return list(self.reviews)

    def is_team_member(self, org: str, team_slug: str, username: str) -> bool:
        members = self.team_members.get(team_slug, [])
        return username in members

    def get_all_requested_teams(self, pr_number: int) -> List[str]:
        return list(self.requested_teams_timeline)


MOCK_EVENT = {
    "pull_request": {
        "number": 42,
        "html_url": "https://github.com/example/repo/pull/42",
        "head": {"repo": {"fork": False}},
    }
}


@pytest.mark.parametrize(
    "messages, reviews, reactions, expected_emojis",
    [
        pytest.param(
            [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="approved", username="alice")],
            [],
            ["test_review_started", "test_approved"],
            id="approval",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="changes_requested", username="alice")],
            [],
            ["test_review_started", "test_needs_change"],
            id="changes_requested",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="commented", username="alice")],
            [],
            ["test_review_started", "test_commented"],
            id="comment",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="changes_requested", username="alice"), Review(state="approved", username="alice")],
            [Reaction(emoji="test_needs_change", user_ids=["U1234"])],
            ["test_review_started", "test_approved"],
            id="approved-from-changes-requested",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="commented", username="alice"), Review(state="approved", username="alice")],
            [Reaction(emoji="test_commented", user_ids=["U1234"])],
            ["test_review_started", "test_approved"],
            id="approved-from-commented",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="changes_requested", username="alice"), Review(state="comment", username="bob")],
            [],
            ["test_review_started", "test_needs_change"],
            id="commented-ignored-when-changes-requested",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="changes_requested", username="alice"), Review(state="approved", username="bob")],
            [],
            ["test_review_started", "test_needs_change"],
            id="approved-ignored-when-changes-requested",
        ),
        pytest.param(
            [Message(text="Need :eyes: but I've got no PR URL", timestamp="yyyy-mm-dd")],
            [Review(state="approved", username="alice")],
            [],
            [],
            id="message-not-found",
        ),
    ],
)
def test_on_pull_request_review(
    messages: List[Message], reviews: List[Review], reactions: List[Reaction], expected_emojis: set
) -> None:
    slack_backend = MockSlackBackend(messages=messages, target_message=messages[0], reactions=reactions)
    github_backend = MockGithubBackend(
        reviews=reviews,
        event=MOCK_EVENT,
        pr=PullRequest(state="open", merged=False, mergeable_state="clean"),
    )

    config = Config(
        slack_client=SlackClient(backend=slack_backend),
        github_client=GithubClient(backend=github_backend),
        slack_channel_id="C1234",
        slapr_bot_user_id="U1234",
        number_of_approvals_required=1,
        emoji_review_started="test_review_started",
        emoji_approved="test_approved",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
        emoji_commented="test_commented",
    )
    slapr.main(config)

    assert slack_backend.emojis == expected_emojis


@pytest.mark.parametrize(
    "event, pr, reactions, expected_emojis",
    [
        pytest.param(
            MOCK_EVENT,
            PullRequest(state="closed", merged=True, mergeable_state="clean"),
            [
                Reaction(emoji="test_review_started", user_ids=["U1234"]),
                Reaction(emoji="test_approved", user_ids=["U1234"]),
            ],
            ["test_review_started", "test_approved", "test_merged"],
            id="merge-approved-pr",
        ),
        pytest.param(
            MOCK_EVENT,
            PullRequest(state="closed", merged=False, mergeable_state="clean"),
            [
                Reaction(emoji="test_review_started", user_ids=["U1234"]),
                Reaction(emoji="test_approved", user_ids=["U1234"]),
            ],
            ["test_review_started", "test_approved", "test_closed"],
            id="merge-approved-pr",
        ),
    ],
)
def test_on_pull_request(event: dict, pr: PullRequest, reactions: List[Reaction], expected_emojis: set) -> None:
    messages = [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")]
    reviews = [Review(state="approved", username="alice")]

    slack_backend = MockSlackBackend(messages=messages, target_message=messages[0], reactions=reactions)
    github_backend = MockGithubBackend(
        reviews=reviews,
        event=event,
        pr=pr,
    )

    config = Config(
        slack_client=SlackClient(backend=slack_backend),
        github_client=GithubClient(backend=github_backend),
        slack_channel_id="C1234",
        slapr_bot_user_id="U1234",
        number_of_approvals_required=1,
        emoji_review_started="test_review_started",
        emoji_approved="test_approved",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
        emoji_commented="test_commented",
    )
    slapr.main(config)

    assert slack_backend.emojis == expected_emojis


# --- Review Map integration tests ---

MOCK_EVENT_WITH_TEAMS = {
    "pull_request": {
        "number": 42,
        "html_url": "https://github.com/example/repo/pull/42",
        "head": {"repo": {"fork": False, "owner": {"login": "datadog"}}},
        "requested_teams": [{"slug": "agent-apm"}],
    },
    "review": {
        "user": {"login": "alice"},
    },
}

MOCK_EVENT_MERGE_WITH_OWNER = {
    "pull_request": {
        "number": 42,
        "html_url": "https://github.com/example/repo/pull/42",
        "head": {"repo": {"fork": False, "owner": {"login": "datadog"}}},
        "state": "closed",
        "requested_teams": [],
    },
}


def test_review_with_review_map_routes_to_team_channel():
    """When a reviewer is a member of a mapped team, emoji goes to that team's channel."""
    messages = [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="ts-apm")]

    slack_backend = MockSlackBackend(
        messages=[],
        target_message=messages[0],
        reactions=[],
        channel_messages={"C_APM": messages},
        channel_reactions={"C_APM": []},
    )
    github_backend = MockGithubBackend(
        reviews=[Review(state="approved", username="alice")],
        event=MOCK_EVENT_WITH_TEAMS,
        pr=PullRequest(state="open", merged=False, mergeable_state="clean"),
        team_members={"agent-apm": ["alice"]},
        requested_teams_timeline=["agent-apm"],
    )

    review_map = ReviewMap(
        team_to_channel={"@datadog/agent-apm": "C_APM"},
        default_channel_id="C_DEFAULT",
    )

    config = Config(
        slack_client=SlackClient(backend=slack_backend),
        github_client=GithubClient(backend=github_backend),
        slack_channel_id="C_DEFAULT",
        slapr_bot_user_id="U1234",
        number_of_approvals_required=1,
        emoji_review_started="test_review_started",
        emoji_approved="test_approved",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
        emoji_commented="test_commented",
        review_map=review_map,
    )
    slapr.main(config)

    assert slack_backend.channel_emojis["C_APM"] == ["test_review_started", "test_approved"]


def test_review_with_review_map_falls_back_to_default():
    """When no team matches, falls back to the default channel."""
    messages = [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="ts-default")]

    event_no_teams = {
        "pull_request": {
            "number": 42,
            "html_url": "https://github.com/example/repo/pull/42",
            "head": {"repo": {"fork": False, "owner": {"login": "datadog"}}},
            "requested_teams": [],
        },
        "review": {
            "user": {"login": "bob"},
        },
    }

    slack_backend = MockSlackBackend(
        messages=messages,
        target_message=messages[0],
        reactions=[],
    )
    github_backend = MockGithubBackend(
        reviews=[Review(state="approved", username="bob")],
        event=event_no_teams,
        pr=PullRequest(state="open", merged=False, mergeable_state="clean"),
    )

    review_map = ReviewMap(
        team_to_channel={"@datadog/agent-apm": "C_APM"},
        default_channel_id="C_DEFAULT",
    )

    config = Config(
        slack_client=SlackClient(backend=slack_backend),
        github_client=GithubClient(backend=github_backend),
        slack_channel_id="C_DEFAULT",
        slapr_bot_user_id="U1234",
        number_of_approvals_required=1,
        emoji_review_started="test_review_started",
        emoji_approved="test_approved",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
        emoji_commented="test_commented",
        review_map=review_map,
    )
    slapr.main(config)

    # Falls back to default channel (tracked in self.emojis)
    assert slack_backend.emojis == ["test_review_started", "test_approved"]


def test_merge_with_review_map_targets_requested_team_channels():
    """On merge, emoji is applied to channels of all teams that were ever requested."""
    messages_apm = [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="ts-apm")]

    slack_backend = MockSlackBackend(
        messages=[],
        target_message=messages_apm[0],
        reactions=[],
        channel_messages={"C_APM": messages_apm},
        channel_reactions={"C_APM": [Reaction(emoji="test_review_started", user_ids=["U1234"])]},
    )
    github_backend = MockGithubBackend(
        reviews=[Review(state="approved", username="alice")],
        event=MOCK_EVENT_MERGE_WITH_OWNER,
        pr=PullRequest(state="closed", merged=True, mergeable_state="clean"),
        requested_teams_timeline=["agent-apm"],
        team_members={"agent-apm": ["alice"]},
    )

    review_map = ReviewMap(
        team_to_channel={"@datadog/agent-apm": "C_APM"},
        default_channel_id="C_DEFAULT",
    )

    config = Config(
        slack_client=SlackClient(backend=slack_backend),
        github_client=GithubClient(backend=github_backend),
        slack_channel_id="C_DEFAULT",
        slapr_bot_user_id="U1234",
        number_of_approvals_required=1,
        emoji_review_started="test_review_started",
        emoji_approved="test_approved",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
        emoji_commented="test_commented",
        review_map=review_map,
    )
    slapr.main(config)

    assert "test_approved" in slack_backend.channel_emojis["C_APM"]
    assert "test_merged" in slack_backend.channel_emojis["C_APM"]


def test_review_map_filters_reviews_to_team_members_only():
    """When a non-team-member approved and a team member comments,
    the team channel should show 'commented', not 'approved'."""
    messages = [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="ts-apm")]

    event = {
        "pull_request": {
            "number": 42,
            "html_url": "https://github.com/example/repo/pull/42",
            "head": {"repo": {"fork": False, "owner": {"login": "datadog"}}},
            "requested_teams": [{"slug": "agent-apm"}],
        },
        "review": {
            "user": {"login": "bob"},  # bob is a team member, submitting a comment
        },
    }

    slack_backend = MockSlackBackend(
        messages=[],
        target_message=messages[0],
        reactions=[],
        channel_messages={"C_APM": messages},
        channel_reactions={"C_APM": []},
    )
    github_backend = MockGithubBackend(
        # alice approved (not a team member), bob commented (team member)
        reviews=[Review(state="approved", username="alice"), Review(state="commented", username="bob")],
        event=event,
        pr=PullRequest(state="open", merged=False, mergeable_state="clean"),
        team_members={"agent-apm": ["bob"]},  # only bob is in agent-apm
        requested_teams_timeline=["agent-apm"],
    )

    review_map = ReviewMap(
        team_to_channel={"@datadog/agent-apm": "C_APM"},
        default_channel_id="C_DEFAULT",
    )

    config = Config(
        slack_client=SlackClient(backend=slack_backend),
        github_client=GithubClient(backend=github_backend),
        slack_channel_id="C_DEFAULT",
        slapr_bot_user_id="U1234",
        number_of_approvals_required=1,
        emoji_review_started="test_review_started",
        emoji_approved="test_approved",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
        emoji_commented="test_commented",
        review_map=review_map,
    )
    slapr.main(config)

    # Should show 'commented' (bob's review), NOT 'approved' (alice is not in the team)
    assert slack_backend.channel_emojis["C_APM"] == ["test_review_started", "test_commented"]
