from . import slack, github, settings


def main() -> None:
    event = github.read_event()

    state: str = event["review"]["state"]
    emoji = slack.get_emoji_for_state(state)

    if emoji is None:
        print(f"No emoji configured for {state=!r}")
        return

    pr_url: str = event["pull_request"]["html_url"]

    timestamp = slack.find_timestamp_of_review_requested_message(
        pr_url=pr_url, channel_id=settings.SLACK_CHANNEL_ID
    )

    if timestamp is None:
        print(f"No message found requesting review for {pr_url=!r}")
        return

    slack.add_reaction(
        timestamp=timestamp, emoji=emoji, channel_id=settings.SLACK_CHANNEL_ID
    )
