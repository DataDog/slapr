from typing import List, Optional, Set, Tuple

import itertools

from .config import Config
from .github import Review


def get_for_reviews(reviews: List[Review], emoji_needs_change: str, emoji_approved: str) -> Optional[str]:
    reviews_without_comments = [review for review in reviews if review.state != "commented"]

    reviews_by_author = {
        username: list(reviews)
        for username, reviews in itertools.groupby(reviews_without_comments, key=lambda review: review.username)
    }

    last_reviews = [reviews[-1] for reviews in reviews_by_author.values() if reviews]

    unique_states = {review.state for review in last_reviews}

    if "changes_requested" in unique_states:
        return emoji_needs_change

    if "approved" in unique_states:
        return emoji_approved

    return None


def diff(new_emojis: Set[str], existing_emojis: Set[str]) -> Tuple[Set[str], Set[str]]:
    emojis_to_add = new_emojis - existing_emojis
    emojis_to_remove = existing_emojis - new_emojis
    return emojis_to_add, emojis_to_remove


def sort_emojis(config: Config, emojis: Set[str]) -> List[str]:
    order = [
        config.emoji_review_started,
        config.emoji_needs_change,
        config.emoji_approved,
        config.emoji_closed,
        config.emoji_merged,
    ]
    order_dict = {v: i for i, v in enumerate(order)}
    return sorted(list(emojis), key=lambda e: order_dict[e])
