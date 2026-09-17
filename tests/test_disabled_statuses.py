# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import FrozenSet, List, Optional

import pytest

import slapr
from slapr import statuses
from slapr.config import Config
from slapr.github import GithubClient, PullRequest, Review
from slapr.review_map import ReviewMap
from slapr.slack import Message, Reaction, SlackClient

from .test_slapr import MOCK_EVENT, MockGithubBackend, MockSlackBackend, _user

PR_URL = MOCK_EVENT["pull_request"]["html_url"]
MESSAGES = [Message(text=f"Need review <{PR_URL}>", timestamp="yyyy-mm-dd")]


# --- Parsing ---


@pytest.mark.parametrize(
    "raw, expected",
    [
        pytest.param(None, frozenset(), id="none"),
        pytest.param("", frozenset(), id="empty"),
        pytest.param("   ", frozenset(), id="whitespace-only"),
        pytest.param("commented", frozenset({"commented"}), id="single"),
        pytest.param("review-started, commented", frozenset({"review-started", "commented"}), id="multiple"),
        pytest.param("  review-started ,commented,  ", frozenset({"review-started", "commented"}), id="trim"),
        pytest.param("commented,commented", frozenset({"commented"}), id="duplicates"),
        pytest.param(
            "review-started,partially-approved,approved,changes-requested,commented,merged,closed",
            statuses.ALL,
            id="all-seven",
        ),
    ],
)
def test_parse_disabled(raw: Optional[str], expected: FrozenSet[str]) -> None:
    assert statuses.parse_disabled(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("review_started", id="underscore-instead-of-dash"),
        pytest.param("Approved", id="wrong-case"),
        pytest.param("commented, banana", id="one-valid-one-unknown"),
        pytest.param("changes_requested", id="github-state-name"),
    ],
)
def test_parse_disabled_rejects_unknown_names(raw: str) -> None:
    with pytest.raises(ValueError, match="Unknown status name"):
        statuses.parse_disabled(raw)


# --- Single channel ---


def _config(slack_backend, github_backend, disabled: FrozenSet[str], **overrides) -> Config:
    kwargs = dict(
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
        disabled_statuses=disabled,
    )
    kwargs.update(overrides)
    return Config(**kwargs)


def _run(
    reviews: List[Review],
    disabled: FrozenSet[str],
    pr: PullRequest = PullRequest(state="open", merged=False, mergeable_state="clean"),
    reactions: Optional[List[Reaction]] = None,
    **overrides,
) -> List[str]:
    slack_backend = MockSlackBackend(messages=MESSAGES, target_message=MESSAGES[0], reactions=reactions or [])
    github_backend = MockGithubBackend(reviews=reviews, event=MOCK_EVENT, pr=pr)
    slapr.main(_config(slack_backend, github_backend, disabled, **overrides))
    return slack_backend.emojis


def test_default_is_unchanged() -> None:
    assert _run([Review(state="approved", user=_user("alice"))], frozenset()) == [
        "test_review_started",
        "test_approved",
    ]


@pytest.mark.parametrize(
    "reviews, disabled, expected",
    [
        pytest.param(
            [Review(state="approved", user=_user("alice"))],
            frozenset({"review-started"}),
            ["test_approved"],
            id="disable-review-started",
        ),
        pytest.param(
            [Review(state="commented", user=_user("alice"))],
            frozenset({"commented"}),
            ["test_review_started"],
            id="disable-commented",
        ),
        pytest.param(
            [Review(state="approved", user=_user("alice"))],
            frozenset({"approved"}),
            ["test_review_started"],
            id="disable-approved",
        ),
        pytest.param(
            [Review(state="commented", user=_user("alice"))],
            frozenset({"review-started", "commented"}),
            [],
            id="disable-multiple-nothing-left",
        ),
        pytest.param(
            [Review(state="changes_requested", user=_user("alice")), Review(state="approved", user=_user("bob"))],
            frozenset({"changes-requested"}),
            ["test_review_started"],
            id="disable-changes-requested-does-not-show-approved",
        ),
        pytest.param(
            [Review(state="changes_requested", user=_user("alice")), Review(state="commented", user=_user("bob"))],
            frozenset({"changes-requested"}),
            ["test_review_started"],
            id="disable-changes-requested-does-not-show-commented",
        ),
        pytest.param(
            [Review(state="approved", user=_user("alice")), Review(state="commented", user=_user("bob"))],
            frozenset({"approved"}),
            ["test_review_started"],
            id="disable-approved-does-not-show-commented",
        ),
    ],
)
def test_disabled_statuses_single_channel(reviews: List[Review], disabled: FrozenSet[str], expected: List[str]) -> None:
    assert _run(reviews, disabled) == expected


def test_disable_partially_approved() -> None:
    reviews = [Review(state="approved", user=_user("alice"))]
    kwargs = dict(number_of_approvals_required=2, emoji_partially_approved="test_partial")
    assert _run(reviews, frozenset(), **kwargs) == ["test_review_started", "test_partial"]
    # Disabling partially-approved does not promote to approved (still below the required count).
    assert _run(reviews, frozenset({"partially-approved"}), **kwargs) == ["test_review_started"]


@pytest.mark.parametrize(
    "pr, disabled, expected",
    [
        pytest.param(
            PullRequest(state="closed", merged=True, mergeable_state="unknown"),
            frozenset({"merged"}),
            [],
            id="disable-merged",
        ),
        pytest.param(
            PullRequest(state="closed", merged=False, mergeable_state="unknown"),
            frozenset({"closed"}),
            [],
            id="disable-closed",
        ),
        pytest.param(
            PullRequest(state="closed", merged=True, mergeable_state="unknown"),
            frozenset({"closed"}),
            ["test_merged"],
            id="disable-closed-keeps-merged",
        ),
        pytest.param(
            PullRequest(state="closed", merged=False, mergeable_state="unknown"),
            frozenset({"merged"}),
            ["test_closed"],
            id="disable-merged-keeps-closed",
        ),
    ],
)
def test_disabled_statuses_on_pull_request_close(
    pr: PullRequest, disabled: FrozenSet[str], expected: List[str]
) -> None:
    assert _run([], disabled, pr=pr) == expected


def test_disabled_status_emoji_is_removed_if_already_present() -> None:
    """Existing bot reactions for a now-disabled status are cleaned up like any other obsolete reaction."""
    reactions = [
        Reaction(emoji="test_review_started", user_ids=["U1234"]),
        Reaction(emoji="test_commented", user_ids=["U1234"]),
    ]
    result = _run(
        [Review(state="commented", user=_user("alice"))],
        frozenset({"commented"}),
        reactions=reactions,
    )
    assert result == ["test_review_started"]


def test_disabled_status_does_not_touch_other_users_reactions() -> None:
    reactions = [Reaction(emoji="test_commented", user_ids=["U_SOMEONE_ELSE"])]
    slack_backend = MockSlackBackend(messages=MESSAGES, target_message=MESSAGES[0], reactions=reactions)
    github_backend = MockGithubBackend(
        reviews=[Review(state="commented", user=_user("alice"))],
        event=MOCK_EVENT,
        pr=PullRequest(state="open", merged=False, mergeable_state="clean"),
    )
    slapr.main(_config(slack_backend, github_backend, frozenset({"commented"})))
    assert slack_backend.emojis == ["test_commented", "test_review_started"]


# --- Review map ---


def _review_map_setup(disabled: FrozenSet[str], reviews: List[Review]):
    messages_apm = [Message(text=f"Need review <{PR_URL}>", timestamp="ts-apm")]
    messages_build = [Message(text=f"Need review <{PR_URL}>", timestamp="ts-build")]
    slack_backend = MockSlackBackend(
        messages=[],
        target_message=messages_apm[0],
        reactions=[],
        channel_messages={"C_APM": messages_apm, "C_BUILD": messages_build},
        channel_reactions={"C_APM": [], "C_BUILD": []},
    )
    github_backend = MockGithubBackend(
        reviews=reviews,
        event=MOCK_EVENT,
        pr=PullRequest(state="open", merged=False, mergeable_state="clean"),
        team_members={"agent-apm": ["alice"], "agent-build": ["bob"]},
        requested_teams_timeline=["agent-apm", "agent-build"],
    )
    review_map = ReviewMap(
        team_to_channel={"@datadog/agent-apm": "C_APM", "@datadog/agent-build": "C_BUILD"},
        default_channel_id="C_DEFAULT",
    )
    config = _config(slack_backend, github_backend, disabled, slack_channel_id="C_DEFAULT", review_map=review_map)
    return slack_backend, config


def test_review_map_disable_review_started_suppresses_broadcast() -> None:
    slack_backend, config = _review_map_setup(
        frozenset({"review-started"}), [Review(state="approved", user=_user("alice"))]
    )
    slapr.main(config)
    assert slack_backend.channel_emojis["C_APM"] == ["test_approved"]
    # The review_started broadcast to other requested teams' channels is disabled too.
    assert slack_backend.channel_emojis["C_BUILD"] == []


def test_review_map_disable_approved_keeps_broadcast() -> None:
    slack_backend, config = _review_map_setup(frozenset({"approved"}), [Review(state="approved", user=_user("alice"))])
    slapr.main(config)
    assert slack_backend.channel_emojis["C_APM"] == ["test_review_started"]
    assert slack_backend.channel_emojis["C_BUILD"] == ["test_review_started"]


def test_review_map_disable_changes_requested_does_not_show_approved() -> None:
    slack_backend, config = _review_map_setup(
        frozenset({"changes-requested"}),
        [Review(state="changes_requested", user=_user("alice"))],
    )
    slapr.main(config)
    assert slack_backend.channel_emojis["C_APM"] == ["test_review_started"]


def test_empty_emoji_is_not_treated_as_disabled() -> None:
    """An empty emoji name is a misconfiguration and must still reach Slack, not be hidden."""
    slack_backend = MockSlackBackend(messages=MESSAGES, target_message=MESSAGES[0], reactions=[])
    github_backend = MockGithubBackend(
        reviews=[], event=MOCK_EVENT, pr=PullRequest(state="closed", merged=True, mergeable_state="unknown")
    )
    slapr.main(_config(slack_backend, github_backend, frozenset(), emoji_merged=""))
    assert slack_backend.emojis == [""]
