from .config import Config
from . import emojis


def main(config: Config) -> None:
    slack = config.slack_client
    github = config.github_client

    event = github.read_event()

    pr_number: int = event["pull_request"]["number"]
    pr = github.get_pr(pr_number=pr_number)
    reviews = github.get_pr_reviews(pr_number=pr_number)
    review_emoji = emojis.get_for_reviews(
        reviews, emoji_needs_change=config.emoji_needs_change, emoji_approved=config.emoji_approved
    )

    pr_url: str = event["pull_request"]["html_url"]
    print(f"Event PR: {pr_url}")
    timestamp = slack.find_timestamp_of_review_requested_message(pr_url=pr_url, channel_id=config.slack_channel_id)
    print(f"Slack message timestamp: {timestamp}")

    if timestamp is None:
        print(f"No message found requesting review for PR: {pr_url}")
        return

    existing_emojis = slack.get_emojis_for_user(
        timestamp=timestamp, channel_id=config.slack_channel_id, user_id=config.slapr_bot_user_id
    )
    print(f"Existing emojis: {', '.join(existing_emojis)}")

    # Review emoji
    new_emojis = {config.emoji_review_started}
    if review_emoji:
        new_emojis.add(review_emoji)

    # PR emoji
    print(f"Is merged: {pr.merged}")
    print(f"Mergeable state: {pr.mergeable_state}")

    if pr.merged:
        new_emojis.add(config.emoji_merged)
    elif pr.state == 'closed':
        new_emojis.add(config.emoji_closed)

    # Add emojis
    emojis_to_add, emojis_to_remove = emojis.diff(new_emojis=new_emojis, existing_emojis=existing_emojis)

    print(f"Emojis to add    : {', '.join(emojis_to_add)}")
    print(f"Emojis to remove : {', '.join(emojis_to_remove)}")

    for review_emoji in emojis_to_add:
        slack.add_reaction(
            timestamp=timestamp, emoji=review_emoji, channel_id=config.slack_channel_id,
        )

    for review_emoji in emojis_to_remove:
        slack.remove_reaction(
            timestamp=timestamp, emoji=review_emoji, channel_id=config.slack_channel_id,
        )
