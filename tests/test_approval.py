# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from pathlib import Path
from typing import List

import pytest

from slapr.approval import ApprovalState, evaluate
from slapr.approval_config import ApprovalConfig
from slapr.github import Review


class MockUser:
    def __init__(self, login: str):
        self.login = login


def _reviews(states: List[str]) -> List[Review]:
    return [Review(state=state, user=MockUser(f"reviewer-{index}")) for index, state in enumerate(states)]


@pytest.mark.parametrize(
    "states, required, expected_state, expected_approvals",
    [
        pytest.param([], 2, ApprovalState.NONE, 0, id="none"),
        pytest.param(["commented"], 2, ApprovalState.COMMENTED, 0, id="commented"),
        pytest.param(["approved"], 2, ApprovalState.PARTIAL, 1, id="partial"),
        pytest.param(["approved", "approved"], 2, ApprovalState.COMPLETE, 2, id="complete"),
        pytest.param(["approved", "approved", "approved"], 2, ApprovalState.COMPLETE, 3, id="above-threshold"),
        pytest.param(["approved", "changes_requested"], 2, ApprovalState.BLOCKED, 1, id="blocked"),
    ],
)
def test_evaluate_approval_progress(
    states: List[str],
    required: int,
    expected_state: ApprovalState,
    expected_approvals: int,
) -> None:
    progress = evaluate(
        reviewer_teams=[],
        reviews=_reviews(states),
        number_of_approvals_required=required,
    )

    assert progress.state == expected_state
    assert progress.approvals == expected_approvals
    assert progress.required == required


def test_evaluate_uses_latest_review_per_author() -> None:
    alice = MockUser("alice")
    bob = MockUser("bob")
    reviews = [
        Review(state="approved", user=alice),
        Review(state="approved", user=bob),
        Review(state="commented", user=alice),
    ]

    progress = evaluate(reviewer_teams=[], reviews=reviews, number_of_approvals_required=2)

    assert progress.state == ApprovalState.PARTIAL
    assert progress.approvals == 1


def test_load_approval_config(tmp_path: Path) -> None:
    config_path = tmp_path / "approval-config.yml"
    config_path.write_text(
        """\
version: 1
states:
  partial:
    - next_track_button
    - one
  complete:
    - ship
  blocked: []
""",
        encoding="utf-8",
    )

    config = ApprovalConfig.load(str(config_path))

    assert config.emojis_for(ApprovalState.PARTIAL) == ("next_track_button", "one")
    assert config.emojis_for(ApprovalState.COMPLETE) == ("ship",)
    assert config.emojis_for(ApprovalState.BLOCKED) == ()
    assert config.emojis_for(ApprovalState.NONE) == ()
    assert config.ordered_emojis == ("next_track_button", "one", "ship")


@pytest.mark.parametrize(
    "contents, expected_error",
    [
        pytest.param("[]", "must be a mapping", id="root-not-mapping"),
        pytest.param("version: 2\nstates: {}", "version must be 1", id="unsupported-version"),
        pytest.param("version: 1\nstates: []", "states must be a mapping", id="states-not-mapping"),
        pytest.param("version: 1\nstates: {}\nextra: true", "unknown approval config keys: extra", id="unknown-key"),
        pytest.param("version: 1\nstates:\n  waiting: []", "unknown approval states: waiting", id="unknown-state"),
        pytest.param(
            "version: 1\nstates:\n  partial: next_track_button",
            "must contain a list",
            id="state-not-list",
        ),
        pytest.param(
            "version: 1\nstates:\n  partial: [ship, ship]",
            "contains duplicate emoji 'ship'",
            id="duplicate-in-state",
        ),
        pytest.param(
            "version: 1\nstates:\n  partial: [ship]\n  complete: [ship]",
            "assigned to both 'partial' and 'complete'",
            id="duplicate-across-states",
        ),
    ],
)
def test_invalid_approval_config(tmp_path: Path, contents: str, expected_error: str) -> None:
    config_path = tmp_path / "approval-config.yml"
    config_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=expected_error):
        ApprovalConfig.load(str(config_path))


def test_legacy_inputs_create_equivalent_rules() -> None:
    config = ApprovalConfig.from_legacy(
        emoji_commented="comment",
        emoji_needs_change="changes_requested",
        emoji_partially_approved="next_track_button",
        emoji_approved="ship",
    )

    assert config.emojis_for(ApprovalState.COMMENTED) == ("comment",)
    assert config.emojis_for(ApprovalState.BLOCKED) == ("changes_requested",)
    assert config.emojis_for(ApprovalState.PARTIAL) == ("next_track_button",)
    assert config.emojis_for(ApprovalState.COMPLETE) == ("ship",)
