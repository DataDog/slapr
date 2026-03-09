# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import List, Set

from . import emojis
from .config import Config
from .github import GithubClient
from .slack import SlackClient




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
    review_emoji = emojis.get_for_reviews(
        reviews,
        emoji_commented=config.emoji_commented,
        emoji_needs_change=config.emoji_needs_change,
        emoji_approved=config.emoji_approved,
        number_of_approvals_required=config.number_of_approvals_required,
    )

    pr_url: str = event["pull_request"]["html_url"]
    print(f"Event PR: {pr_url}")

    # Build the set of emojis to apply
    new_emojis = {config.emoji_review_started}
    if review_emoji:
        new_emojis.add(review_emoji)

    print(f"Is merged: {pr.merged}")
    print(f"Mergeable state: {pr.mergeable_state}")

    if pr.merged:
        new_emojis.add(config.emoji_merged)
    elif pr.state == "closed":
        new_emojis.add(config.emoji_closed)

    # Determine target channels
    target_channels = _resolve_target_channels(config, github, event, pr_number)

    # Apply emojis to each target channel
    for channel_id in target_channels:
        _apply_emojis_to_channel(config, slack, new_emojis, pr_url, channel_id)


def _apply_emojis_to_channel(
    config: Config,
    slack: SlackClient,
    new_emojis: Set[str],
    pr_url: str,
    channel_id: str,
) -> None:
    timestamp = slack.find_timestamp_of_review_requested_message(pr_url=pr_url, channel_id=channel_id)
    print(f"Slack message timestamp for channel {channel_id}: {timestamp}")

    if timestamp is None:
        print(f"No message found requesting review for PR: {pr_url} in channel {channel_id}")
        return

    existing_emojis = slack.get_emojis_for_user(
        timestamp=timestamp, channel_id=channel_id, user_id=config.slapr_bot_user_id
    )
    print(f"Existing emojis: {', '.join(existing_emojis)}")

    emojis_to_add, emojis_to_remove = emojis.diff(new_emojis=new_emojis, existing_emojis=existing_emojis)

    sorted_emojis_to_add = sorted(emojis_to_add, key=config.emojis_by_review_step)

    print(f"Emojis to add (ordered) : {', '.join(sorted_emojis_to_add)}")
    print(f"Emojis to remove        : {', '.join(emojis_to_remove)}")

    for emoji in sorted_emojis_to_add:
        slack.add_reaction(timestamp=timestamp, emoji=emoji, channel_id=channel_id)

    for emoji in emojis_to_remove:
        slack.remove_reaction(timestamp=timestamp, emoji=emoji, channel_id=channel_id)


def _resolve_target_channels(config: Config, github: GithubClient, event: dict, pr_number: int) -> List[str]:
    """Determine which Slack channels to target based on the review map."""
    review_map = config.review_map
    if review_map is None:
        return [config.slack_channel_id]

    org = event["pull_request"]["head"]["repo"]["owner"]["login"]

    pr_state = event["pull_request"].get("state", "open")

    # For merge/close events, use Timeline API to get all teams ever requested
    if pr_state == "closed":
        all_requested_teams = github.get_all_requested_teams(pr_number)
        target_channels = set()
        for team_slug in all_requested_teams:
            full_team = f"@{org}/{team_slug}".lower()
            if full_team in review_map.team_to_channel:
                target_channels.add(review_map.team_to_channel[full_team])
        if target_channels:
            return list(target_channels)
        return [config.slack_channel_id]

    # For review events, determine target channels from reviewer's team membership
    reviewer = event.get("review", {}).get("user", {}).get("login")
    requested_teams = [t["slug"] for t in event["pull_request"].get("requested_teams", [])]

    target_channels = []
    for team_slug in requested_teams:
        full_team = f"@{org}/{team_slug}".lower()
        if full_team in review_map.team_to_channel and reviewer and github.is_team_member(org, team_slug, reviewer):
            target_channels.append(review_map.team_to_channel[full_team])

    if target_channels:
        return target_channels
    return [config.slack_channel_id]
