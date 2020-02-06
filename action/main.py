import itertools
from typing import List, Optional, Set, Tuple

from . import github, settings, slack


def get_emoji_for_reviews(reviews: List[github.Review]) -> Optional[str]:
    reviews_without_comments = [
        review for review in reviews if review.state != "commented"
    ]

    reviews_by_author = {
        username: list(reviews)
        for username, reviews in itertools.groupby(
            reviews_without_comments, key=lambda review: review.username
        )
    }

    last_reviews = [reviews[-1] for reviews in reviews_by_author.values() if reviews]

    unique_states = {review.state for review in last_reviews}

    if "changes_requested" in unique_states:
        return settings.EMOJI_NEEDS_CHANGES

    if "approved" in unique_states:
        return settings.EMOJI_READY_TO_MERGE

    return None


def diff_emojis(new_emojis: Set[str], existing_emojis: Set[str]) -> Tuple[Set[str], Set[str]]:
    emojis_to_add = new_emojis - existing_emojis
    emojis_to_remove = existing_emojis - new_emojis
    return emojis_to_add, emojis_to_remove


def main() -> None:
    event = github.read_event()

    pr_number: int = event["pull_request"]["number"]
    reviews = github.get_pr_reviews(pr_number=pr_number)
    review_emoji = get_emoji_for_reviews(reviews)

    pr_url: str = event["pull_request"]["html_url"]
    print(f"Event PR: {pr_url}")
    timestamp = slack.find_timestamp_of_review_requested_message(
        pr_url=pr_url, channel_id=settings.SLACK_CHANNEL_ID
    )
    print(f"Slack message timestamp: {timestamp}")

    if timestamp is None:
        print(f"No message found requesting review for PR: {pr_url}")
        return

    existing_emojis = slack.get_emojis(timestamp=timestamp, channel_id=settings.SLACK_CHANNEL_ID)
    print(f"Existing emojis: {', '.join(existing_emojis)}")

    new_emojis = {settings.EMOJI_REVIEW_STARTED}
    if review_emoji:
        new_emojis.add(review_emoji)

    if review_emoji is None:
        emojis_to_add = new_emojis
        emojis_to_remove = existing_emojis
    else:
        emojis_to_add, emojis_to_remove = diff_emojis(new_emojis, existing_emojis=existing_emojis)

    print(f"Emojis to add    : {', '.join(emojis_to_add)}")
    print(f"Emojis to remove : {', '.join(emojis_to_remove)}")

    for review_emoji in emojis_to_add:
        slack.add_reaction(
            timestamp=timestamp, emoji=review_emoji, channel_id=settings.SLACK_CHANNEL_ID
        )

    for review_emoji in emojis_to_remove:
        slack.remove_reaction(
            timestamp=timestamp, emoji=review_emoji, channel_id=settings.SLACK_CHANNEL_ID
        )
