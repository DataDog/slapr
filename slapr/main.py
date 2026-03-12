# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import Optional, Set, Tuple

from . import emojis
from .config import Config
from .github import GithubClient, Review
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

    pr_url: str = event["pull_request"]["html_url"]
    print(f"Event PR: {pr_url}")

    print(f"Is merged: {pr.merged}")
    print(f"Mergeable state: {pr.mergeable_state}")

    # Determine target channels (with optional team slug for filtering)
    target_channels = _resolve_target_channels(config, github, event, pr_number)

    for channel_id, team_slug in target_channels:
        # Filter reviews to team members only when review-map is active
        if team_slug is not None:
            org = event["pull_request"]["head"]["repo"]["owner"]["login"]
            team_reviews = [r for r in reviews if github.is_team_member(org, team_slug, r.username)]
            print(f"Channel {channel_id} (team {team_slug}): {len(team_reviews)}/{len(reviews)} reviews from team members")
        else:
            team_reviews = reviews

        review_emoji = emojis.get_for_reviews(
            team_reviews,
            emoji_commented=config.emoji_commented,
            emoji_needs_change=config.emoji_needs_change,
            emoji_approved=config.emoji_approved,
            number_of_approvals_required=config.number_of_approvals_required,
        )

        new_emojis = set() if pr.state == "closed" else {config.emoji_review_started}
        if review_emoji:
            new_emojis.add(review_emoji)

        if pr.merged:
            new_emojis.add(config.emoji_merged)
        elif pr.state == "closed":
            new_emojis.add(config.emoji_closed)

        _apply_emojis_to_channel(config, slack, new_emojis, pr_url, channel_id)

    # Broadcast review_started to ALL requested team channels, not just the reviewer's.
    # Only on the first review (len==1) — subsequent reviews already have review_started.
    if config.review_map is not None and not pr.merged and pr.state != "closed" and len(reviews) == 1:
        all_channels = _all_requested_team_channels(config, github, event, pr_number)
        already_processed = {ch for ch, _ in target_channels}
        for channel_id in all_channels - already_processed:
            print(f"Broadcasting review_started to channel {channel_id}")
            _apply_emojis_to_channel(
                config, slack, {config.emoji_review_started}, pr_url, channel_id
            )


def _all_requested_team_channels(
    config: Config, github: GithubClient, event: dict, pr_number: int
) -> Set[str]:
    """Return all Slack channel IDs for teams requested on this PR."""
    review_map = config.review_map
    if review_map is None:
        return set()
    org = event["pull_request"]["head"]["repo"]["owner"]["login"]
    all_teams = github.get_all_requested_teams(pr_number)
    channels = set()
    for team_slug in all_teams:
        full_team = f"@{org}/{team_slug}".lower()
        if full_team in review_map.team_to_channel:
            channels.add(review_map.team_to_channel[full_team])
    return channels


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


def _resolve_target_channels(
    config: Config, github: GithubClient, event: dict, pr_number: int
) -> Set[Tuple[str, Optional[str]]]:
    """Determine which Slack channels to target based on the review map.

    Use the Timeline API to get all teams ever requested, since submitted reviews
    are removed from the event payload's requested_teams list.
    When PR is closed (merged or closed), add all requested channels.
    Otherwise add only channels the reviewer belongs to

    Returns a set of (channel_id, team_slug) tuples. team_slug is None
    for legacy mode (no review-map) or fallback to default channel.
    """
    review_map = config.review_map
    if review_map is None:
        return {(config.slack_channel_id, None)}

    org = event["pull_request"]["head"]["repo"]["owner"]["login"]
    pr_state = event["pull_request"].get("state", "open")
    requested_teams = github.get_all_requested_teams(pr_number)
    reviewer = event.get("review", {}).get("user", {}).get("login")

    print(f"Reviewer: {reviewer}")
    print(f"Requested teams (from timeline): {', '.join(requested_teams)}")

    target_channels = set()
    for team_slug in requested_teams:
        full_team = f"@{org}/{team_slug}".lower()
        if full_team not in review_map.team_to_channel:
            print(f"  Team {full_team}: not in review map, skipping")
            continue
        channel_id = review_map.team_to_channel[full_team]
        if pr_state == "closed":
            # Add all channels in this case.
            target_channels.add((channel_id, team_slug))
        else:
            # Or select only channels the reviewer belongs to.
            is_member = reviewer and github.is_team_member(org, team_slug, reviewer)
            print(f"  Team {full_team}: channel={channel_id}, {reviewer} is_member={is_member}")
            if is_member:
                target_channels.add((channel_id, team_slug))

    if target_channels:
        return target_channels
    print(f"No team match, falling back to default channel {config.slack_channel_id}")
    return {(config.slack_channel_id, None)}
