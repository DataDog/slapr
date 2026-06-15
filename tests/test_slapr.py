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


# --- Mock GitHub objects (stand-ins for PyGithub types) ---


class MockUser:
    def __init__(self, login: str):
        self.login = login

    def __repr__(self):
        return f"MockUser({self.login!r})"


class MockTeam:
    def __init__(self, slug: str, members: List[str], organization: "MockOrganization" = None):
        self.slug = slug
        self._members = members
        self.organization = organization

    def has_in_members(self, user) -> bool:
        return user.login in self._members


class MockOrganization:
    def __init__(self, login: str, teams: Dict[str, MockTeam]):
        self.login = login
        self._teams = teams

    def get_team_by_slug(self, slug: str) -> MockTeam:
        return self._teams[slug]


# --- Mock backends ---


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

    def get_organization(self, org: str):
        teams = {
            slug: MockTeam(slug, members)
            for slug, members in self.team_members.items()
        }
        mock_org = MockOrganization(org, teams)
        # Back-link teams to their org (PyGithub Team objects have .organization)
        for team in teams.values():
            team.organization = mock_org
        return mock_org

    def get_user(self, username: str):
        return MockUser(username)

    def get_all_requested_teams(self, org_name: str, pr_number: int) -> List:
        org = self.get_organization(org_name)
        return [org.get_team_by_slug(slug) for slug in self.requested_teams_timeline]


# --- Helper to create mock users for Review construction ---


def _user(login: str) -> MockUser:
    return MockUser(login)


# --- Test data ---


MOCK_EVENT = {
    "pull_request": {
        "number": 42,
        "html_url": "https://github.com/example/repo/pull/42",
        "head": {"repo": {"fork": False, "owner": {"login": "datadog"}}},
    },
    "review": {
        "user": {"login": "alice"},
    },
}


@pytest.mark.parametrize(
    "messages, reviews, reactions, expected_emojis",
    [
        pytest.param(
            [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="approved", user=_user("alice"))],
            [],
            ["test_review_started", "test_approved"],
            id="approval",
        ),
        pytest.param(
            [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="approved", user=_user("alice"), has_inline_comments=True)],
            [],
            ["test_review_started", "test_approved_with_comments"],
            id="approval-with-inline-comments",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="changes_requested", user=_user("alice"))],
            [],
            ["test_review_started", "test_needs_change"],
            id="changes_requested",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="commented", user=_user("alice"))],
            [],
            ["test_review_started", "test_commented"],
            id="comment",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="changes_requested", user=_user("alice")), Review(state="approved", user=_user("alice"))],
            [Reaction(emoji="test_needs_change", user_ids=["U1234"])],
            ["test_review_started", "test_approved"],
            id="approved-from-changes-requested",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="commented", user=_user("alice")), Review(state="approved", user=_user("alice"))],
            [Reaction(emoji="test_commented", user_ids=["U1234"])],
            ["test_review_started", "test_approved"],
            id="approved-from-commented",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="changes_requested", user=_user("alice")), Review(state="commented", user=_user("alice"))],
            [],
            ["test_review_started", "test_commented"],
            id="commented-after-changes-requested-same-reviewer",
        ),
        pytest.param(
            [Message(text="Need :eyes: but I've got no PR URL", timestamp="yyyy-mm-dd")],
            [Review(state="approved", user=_user("alice"))],
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
        emoji_approved_with_comments="test_approved_with_comments",
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
            ["test_approved", "test_merged"],
            id="merge-approved-pr",
        ),
        pytest.param(
            MOCK_EVENT,
            PullRequest(state="closed", merged=False, mergeable_state="clean"),
            [
                Reaction(emoji="test_review_started", user_ids=["U1234"]),
                Reaction(emoji="test_approved", user_ids=["U1234"]),
            ],
            ["test_approved", "test_closed"],
            id="close-approved-pr",
        ),
    ],
)
def test_on_pull_request(event: dict, pr: PullRequest, reactions: List[Reaction], expected_emojis: set) -> None:
    messages = [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")]
    reviews = [Review(state="approved", user=_user("alice"))]

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
        emoji_approved_with_comments="test_approved_with_comments",
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
        reviews=[Review(state="approved", user=_user("alice"))],
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
        emoji_approved_with_comments="test_approved_with_comments",
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
        reviews=[Review(state="approved", user=_user("bob"))],
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
        emoji_approved_with_comments="test_approved_with_comments",
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
        reviews=[Review(state="approved", user=_user("alice"))],
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
        emoji_approved_with_comments="test_approved_with_comments",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
        emoji_commented="test_commented",
        review_map=review_map,
    )
    slapr.main(config)

    assert slack_backend.channel_emojis["C_APM"] == ["test_approved", "test_merged"]


def test_review_map_uses_reviewer_state_only():
    """Only reviews from the reviewer's team members determine the emoji."""
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
        reviews=[Review(state="approved", user=_user("alice")), Review(state="commented", user=_user("bob"))],
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
        emoji_approved_with_comments="test_approved_with_comments",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
        emoji_commented="test_commented",
        review_map=review_map,
    )
    slapr.main(config)

    # Only bob's review (commented) counts — alice's approval is ignored
    assert slack_backend.channel_emojis["C_APM"] == ["test_review_started", "test_commented"]


def test_review_started_broadcast_to_all_requested_team_channels():
    """When a reviewer from team-A approves, review_started should also appear
    on team-B's channel if team-B was requested for review."""
    messages_apm = [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="ts-apm")]
    messages_build = [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="ts-build")]

    event = {
        "pull_request": {
            "number": 42,
            "html_url": "https://github.com/example/repo/pull/42",
            "head": {"repo": {"fork": False, "owner": {"login": "datadog"}}},
            "requested_teams": [{"slug": "agent-apm"}, {"slug": "agent-build"}],
        },
        "review": {
            "user": {"login": "alice"},
        },
    }

    slack_backend = MockSlackBackend(
        messages=[],
        target_message=messages_apm[0],
        reactions=[],
        channel_messages={"C_APM": messages_apm, "C_BUILD": messages_build},
        channel_reactions={"C_APM": [], "C_BUILD": []},
    )
    github_backend = MockGithubBackend(
        reviews=[Review(state="approved", user=_user("alice"))],
        event=event,
        pr=PullRequest(state="open", merged=False, mergeable_state="clean"),
        team_members={"agent-apm": ["alice"], "agent-build": ["bob"]},
        requested_teams_timeline=["agent-apm", "agent-build"],
    )

    review_map = ReviewMap(
        team_to_channel={"@datadog/agent-apm": "C_APM", "@datadog/agent-build": "C_BUILD"},
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
        emoji_approved_with_comments="test_approved_with_comments",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
        emoji_commented="test_commented",
        review_map=review_map,
    )
    slapr.main(config)

    # alice is in agent-apm: full review status
    assert slack_backend.channel_emojis["C_APM"] == ["test_review_started", "test_approved"]
    # agent-build was also requested: should get review_started even though alice is not a member
    assert slack_backend.channel_emojis["C_BUILD"] == ["test_review_started"]
