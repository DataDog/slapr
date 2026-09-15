# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from enum import Enum
from typing import List, NamedTuple, Optional

from .github import Review


class ApprovalState(str, Enum):
    NONE = "none"
    COMMENTED = "commented"
    PARTIAL = "partial"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ApprovalProgress(NamedTuple):
    state: ApprovalState
    approvals: Optional[int]
    required: Optional[int]


def evaluate(reviewer_teams: List, reviews: List[Review], number_of_approvals_required: int) -> ApprovalProgress:
    last_review_by_author = {review.user.login: review for review in reviews}

    if reviewer_teams:
        last_reviews = [
            review
            for review in last_review_by_author.values()
            if any(team.has_in_members(review.user) for team in reviewer_teams)
        ]
    else:
        last_reviews = list(last_review_by_author.values())

    unique_states = {review.state for review in last_reviews}
    approval_count = len([review for review in last_reviews if review.state == "approved"])

    if "changes_requested" in unique_states:
        state = ApprovalState.BLOCKED
    elif approval_count >= number_of_approvals_required:
        state = ApprovalState.COMPLETE
    elif approval_count > 0:
        state = ApprovalState.PARTIAL
    elif "commented" in unique_states:
        state = ApprovalState.COMMENTED
    else:
        state = ApprovalState.NONE

    return ApprovalProgress(
        state=state,
        approvals=approval_count,
        required=number_of_approvals_required,
    )
