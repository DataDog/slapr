# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

import os
from . import emojis
from .config import Config


# TODO: Clean
def get_team_to_channel(team_groups_contents):
    import re
    import json

    RE_TEAM_GROUPS = re.compile(r'.*teamGroups.*= ({.*});', re.DOTALL | re.MULTILINE)
    RE_COMMENTS = re.compile(r'//.*', re.MULTILINE)
    RE_REPLACE_SLACK_URL = re.compile(r'`\$\{SLACK_URL\}/(.+)`', re.MULTILINE)
    RE_REPLACE_KEYS = re.compile(r'(?<=[^a-zA-Z0-9_])[a-zA-Z0-9_]+(?=:)', re.MULTILINE)
    RE_COMMAS = re.compile(r',([}\],])', re.MULTILINE)

    # TS -> JSON
    team_groups = RE_TEAM_GROUPS.match(team_groups_contents).group(1)
    team_groups = RE_COMMENTS.sub('\n', team_groups)
    team_groups = RE_REPLACE_SLACK_URL.sub(lambda match: f'"{match.group(1)}"', team_groups)
    team_groups = team_groups.replace("'", '"')
    team_groups = team_groups.replace(' ', '')
    team_groups = team_groups.replace('\n', '')
    team_groups = RE_COMMAS.sub(lambda match: match.group(1), team_groups)
    team_groups = RE_REPLACE_KEYS.sub(lambda match: f'"{match.group(0)}"', team_groups)

    team_groups = json.loads(team_groups)

    team_to_channel = {team: team_groups[team]['slackChannel'] for team in team_groups}

    return team_to_channel


def get_teams(user):
    """Get teams of one user."""

    import github

    # TODO: pass as arg
    _gh = github.Github(os.environ["GITHUB_TOKEN"])
    repo = _gh.get_repo('DataDog/datadog-agent')
    user = _gh.get_user(user)
    teams = [team.name for team in repo.get_teams() if team.has_in_members(user) and team.name != 'Dev']

    assert len(teams) > 0, f'No team found for user {user}'

    return teams


def get_team_groups_contents():
    import github

    # TODO: pass as arg
    _gh = github.Github(os.environ["GITHUB_TOKEN"])
    repo = _gh.get_repo('DataDog/web-ui')
    contents = str(repo.get_contents('packages/lib/teams/teams-config.ts').decoded_content, 'utf-8')

    return contents


class TeamState:
    APPROVED = 'APPROVED'
    APPROVED_COMMENTS = 'APPROVED_COMMENTS'
    COMMENTED = 'COMMENTED'
    CHANGES_REQUESTED = 'CHANGES_REQUESTED'


def get_team_state(user_states: set[str]) -> str:
    """Deduce overall team state from all reviews of multiple members of the same team."""

    if TeamState.CHANGES_REQUESTED in user_states:
        return TeamState.CHANGES_REQUESTED

    if TeamState.APPROVED in user_states:
        if TeamState.COMMENTED in user_states:
            return TeamState.APPROVED_COMMENTS
        else:
            return TeamState.APPROVED

    return TeamState.COMMENTED


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

    if config.slapr_multichannel:
        print('Multi channel enabled')

        # Get review for each user
        user_reviews = {}
        for review in reviews:
            user_reviews[review.username] = review.state

        # Aggregate user reviews by team
        from collections import defaultdict
        team_reviews = defaultdict(set)
        for user, review in user_reviews.items():
            teams = get_teams(user)
            print(f"User: {user}, Review: {review}, Teams: {teams}")
            for team in teams:
                team_reviews[team].add(review)

        # Aggregate team reviews by channel
        channel_reviews = defaultdict(set)
        team_to_channel = get_team_to_channel(get_team_groups_contents())
        for team, reviews in team_reviews.items():
            print(f'Team: {team}, Reviews: {reviews}')
            channel = team_to_channel[team]
            channel_reviews[channel].update(reviews)

        # Get overall state for each channel
        channel_reviews = {channel: get_team_state(reviews) for channel, reviews in channel_reviews.items()}

        # Update each channel
        for channel, review in channel_reviews.items():
            print(channel, review)
    else:
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
                channel_id=config.slack_channel_id,
            )

        for review_emoji in emojis_to_remove:
            slack.remove_reaction(
                timestamp=timestamp,
                emoji=review_emoji,
                channel_id=config.slack_channel_id,
            )
