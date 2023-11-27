# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2020-present Datadog, Inc.

from typing import List, Optional, Set, Tuple

import itertools

from .github import Review


def get_for_reviews(reviews: List[Review], emoji_needs_change: str, emoji_approved: str, number_of_approvals_required: int) -> Optional[str]:
    reviews_without_comments = [review for review in reviews if review.state != "commented"]

    reviews_by_author = {
        username: list(reviews)
        for username, reviews in itertools.groupby(reviews_without_comments, key=lambda review: review.username)
    }
    
    approvals = [review.state for review in reviews_without_comments]
    approvalsCount = approvals.count("approved")

    last_reviews = [reviews[-1] for reviews in reviews_by_author.values() if reviews]

    unique_states = {review.state for review in last_reviews}

    if "changes_requested" in unique_states:
        return emoji_needs_change

    if ("approved" in unique_states) and approvalsCount >= number_of_approvals_required:
        return emoji_approved

    return None


def diff(new_emojis: Set[str], existing_emojis: Set[str]) -> Tuple[Set[str], Set[str]]:
    emojis_to_add = new_emojis - existing_emojis
    emojis_to_remove = existing_emojis - new_emojis
    return emojis_to_add, emojis_to_remove
