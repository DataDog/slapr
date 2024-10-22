# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from . import emojis
from .config import Config


def channel_react(slack, pr_url, config, review_emoji, pr, channel_id):
    """React to `channel_id` with `review_emoji` for PR review `pr_url`."""

    print('Reacting to channel', channel_id, 'with emoji', review_emoji)

    timestamp = slack.find_timestamp_of_review_requested_message(pr_url=pr_url, channel_id=channel_id)
    print(f"Slack message timestamp: {timestamp}")

    if timestamp is None:
        print(f"No message found requesting review for PR: {pr_url}")
        return

    existing_emojis = slack.get_emojis_for_user(
        timestamp=timestamp, channel_id=channel_id, user_id=config.slapr_bot_user_id
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
    elif pr.state == "closed":
        new_emojis.add(config.emoji_closed)

    # Add emojis
    emojis_to_add, emojis_to_remove = emojis.diff(new_emojis=new_emojis, existing_emojis=existing_emojis)

    sorted_emojis_to_add = sorted(emojis_to_add, key=config.emojis_by_review_step)

    print(f"Emojis to add (ordered) : {', '.join(sorted_emojis_to_add)}")
    print(f"Emojis to remove        : {', '.join(emojis_to_remove)}")

    for review_emoji in sorted_emojis_to_add:
        slack.add_reaction(
            timestamp=timestamp,
            emoji=review_emoji,
            channel_id=channel_id,
        )

    for review_emoji in emojis_to_remove:
        slack.remove_reaction(
            timestamp=timestamp,
            emoji=review_emoji,
            channel_id=channel_id,
        )


def main(config: Config) -> None:
    slack = config.slack_client
    github = config.github_client

    event = github.read_event()

    is_fork: bool = event["pull_request"]["head"]["repo"]["fork"]

    if is_fork:
        print("Fork PRs are not supported.")
        return

    pr_number: int = event["pull_request"]["number"]
    pr = github.get_pr(pr_number=pr_number)
    reviews = github.get_pr_reviews(pr_number=pr_number)

    pr_url: str = event["pull_request"]["html_url"]
    print(f"Event PR: {pr_url}")

    if config.slapr_multichannel:
        print('Multi channel enabled')

        from .multichannel import get_team_to_channel, get_channel_reviews
        from .github import TeamState

        # TODO : clean
        TEAM_CONFIG_REPO = 'DataDog/web-ui'
        TEAM_CONFIG_FILE = 'packages/lib/teams/teams-config.ts'
        team_to_channel = get_team_to_channel(github.read_file(TEAM_CONFIG_REPO, TEAM_CONFIG_FILE))
        channel_reviews = get_channel_reviews(reviews, team_to_channel, github)
        print(channel_reviews)
        exit()

        channel_reviews = {'C06QEJ59XQF': TeamState.APPROVED, 'C07SHSHS3E3': TeamState.CHANGES_REQUESTED}

        # Update each channel
        for channel, state in channel_reviews.items():
            print(f'Updating review for channel {channel} with state {state}')
            emoji = TeamState.get_emoji(state, config.emoji_approved, config.emoji_commented, config.emoji_needs_change)
            channel_react(slack, pr_url, config, emoji, pr, channel)
    else:
        review_emoji = emojis.get_for_reviews(
            reviews,
            emoji_commented=config.emoji_commented,
            emoji_needs_change=config.emoji_needs_change,
            emoji_approved=config.emoji_approved,
            number_of_approvals_required=config.number_of_approvals_required,
        )
        channel_react(slack, pr_url, config, review_emoji, pr, config.slack_channel_id)
