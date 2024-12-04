# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

import itertools

from .github import Review


def get_for_reviews(
    reviews: list[Review],
    emoji_commented: int,
    emoji_needs_change: str,
    emoji_approved: str,
    number_of_approvals_required: int,
) -> str | None:

    reviews_by_author = {
        username: list(reviews) for username, reviews in itertools.groupby(reviews, key=lambda review: review.username)
    }

    last_reviews = [reviews[-1] for reviews in reviews_by_author.values() if reviews]
    unique_states = {review.state for review in last_reviews}

    if "changes_requested" in unique_states:
        return emoji_needs_change

    approval_count = len([review.state for review in reviews if review.state == "approved"])
    if ("approved" in unique_states) and approval_count >= number_of_approvals_required:
        return emoji_approved

    if "commented" in unique_states:
        return emoji_commented

    return None


def diff(new_emojis: set[str], existing_emojis: set[str]) -> tuple[set[str], set[str]]:
    emojis_to_add = new_emojis - existing_emojis
    emojis_to_remove = existing_emojis - new_emojis
    return emojis_to_add, emojis_to_remove
