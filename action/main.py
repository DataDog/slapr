from typing import Optional

import os
import json


# TODO: Make these configurable.
STATE_TO_EMOJI = {
    "commented": "white_check_mark",
    "approved": "comment",
    "changes_requested": "pray",
}


def find_review_requested_message(pr_url: str) -> Optional[dict]:
    """
    Find a Slack message where author requested a review for the given PR.
    """
    print(f"TODO: find_review_requested_message {pr_url=!r}")
    return None


def add_reaction(message: dict, emoji: str) -> None:
    """
    Add a reaction to a Slack message.

    See: https://api.slack.com/methods/reactions.add
    """
    print(f"TODO: add_reaction {message=!r} {emoji=!r}")


def main() -> None:
    event_path = os.environ["GITHUB_EVENT_PATH"]
    with open(event_path) as f:
        event: dict = json.load(f)

    state: str = event["review"]["state"]
    print(f"Review: {state=!r}")

    emoji = STATE_TO_EMOJI.get(state)

    if emoji is None:
        print(f"No emoji configured for {state=!r}")
        return

    pr_url: str = event["pull_request"]["html_url"]
    message = find_review_requested_message(pr_url)

    if message is None:
        print(f"No message found requesting review for {pr_url=!r}")
        return

    add_reaction(message, emoji=emoji)


if __name__ == "__main__":
    main()
