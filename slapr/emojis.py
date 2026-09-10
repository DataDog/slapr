# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import List, Optional, Set, Tuple

from .github import Review
from .config import Config


def select(
    reviewer_teams: List,
    reviews: List[Review],
    config: Config,
    number_of_approvals_required: int,
) -> Optional[str]:

    last_review_by_author = {review.user.login: review for review in reviews}

    # Keep only reviews from authors belonging to the same team(s) as the reviewer
    if reviewer_teams:
        last_reviews = [
            review
            for review in last_review_by_author.values()
            if any(team.has_in_members(review.user) for team in reviewer_teams)
        ]
    else:
        # No review map or no team match: consider all reviews
        last_reviews = list(last_review_by_author.values())

    unique_states = {review.state for review in last_reviews}

    if "changes_requested" in unique_states:
        return config.emoji_needs_change

    approval_count = len([review.state for review in last_reviews if review.state == "approved"])
    if ("approved" in unique_states) and approval_count >= number_of_approvals_required:
        return config.emoji_approved

    if approval_count > 0 and config.emoji_partially_approved:
        return config.emoji_partially_approved

    if "commented" in unique_states:
        return config.emoji_commented

    return None


def diff(new_emojis: Set[str], existing_emojis: Set[str]) -> Tuple[Set[str], Set[str]]:
    emojis_to_add = new_emojis - existing_emojis
    emojis_to_remove = existing_emojis - new_emojis
    return emojis_to_add, emojis_to_remove
