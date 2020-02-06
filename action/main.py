from typing import List, Optional, Tuple, Set

from . import slack, github, settings


def get_emoji_for_review_states(states: List[str]) -> Optional[str]:
    unique_states = set(states)

    if "changes_requested" in unique_states:
        return settings.EMOJI_NEEDS_CHANGES

    if "approved" in unique_states:
        return settings.EMOJI_READY_TO_MERGE

    return None


def diff_emojis(emoji: str, emojis: Set[str]) -> Tuple[Set[str], Set[str]]:
    emojis_to_add = {emoji} - emojis
    emojis_to_remove = emojis - {emoji}
    return emojis_to_add, emojis_to_remove


def main() -> None:
    event = github.read_event()

    pr_number: int = event["pull_request"]["number"]
    states = github.get_pr_review_states(pr_number=pr_number)
    emoji = get_emoji_for_review_states(states)

    if emoji is None:
        print(f"No emoji found for {states=}")
        return

    pr_url: str = event["pull_request"]["html_url"]
    timestamp = slack.find_timestamp_of_review_requested_message(
        pr_url=pr_url, channel_id=settings.SLACK_CHANNEL_ID
    )

    if timestamp is None:
        print(f"No message found requesting review for {pr_url=!r}")
        return

    emojis = slack.get_emojis(
        timestamp=timestamp, channel_id=settings.SLACK_CHANNEL_ID
    )
    print(f"Existing emojis: {emojis}")

    emojis_to_add, emojis_to_remove = diff_emojis(emoji, emojis=emojis)
    print(f"{emojis_to_add=}")
    print(f"{emojis_to_remove=}")

    for emoji in emojis_to_add:
        print(f"Adding {emoji=!r}")
        slack.add_reaction(
            timestamp=timestamp, emoji=emoji, channel_id=settings.SLACK_CHANNEL_ID
        )

    for emoji in emojis_to_remove:
        print(f"Removing {emoji=!r}")
        slack.remove_reaction(
            timestamp=timestamp, emoji=emoji, channel_id=settings.SLACK_CHANNEL_ID
        )
