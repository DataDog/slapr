# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

import os
from . import emojis
from .config import Config


# TODO: Clean
def get_channel_reviews(reviews, team_to_channel):
    """From the review history, deduce the review state to send to each channel."""

    from collections import defaultdict

    # Get review for each user
    user_reviews = {}
    for review in reviews:
        # TODO: Handle approved + commented case
        user_reviews[review.username] = review.state

    # Aggregate user reviews by team
    team_reviews = defaultdict(set)
    for user, review in user_reviews.items():
        teams = get_teams(user)
        print(f"User: {user}, Review: {review}, Teams: {teams}")
        for team in teams:
            team_reviews[team].add(review)

    # Aggregate team reviews by channel
    channel_reviews = defaultdict(set)
    for team, reviews in team_reviews.items():
        print(f'Team: {team}, Reviews: {reviews}')
        channel = team_to_channel[team]
        channel_reviews[channel].update(reviews)

    # Get overall state for each channel
    channel_reviews = {channel: get_team_state(reviews) for channel, reviews in channel_reviews.items()}

    return channel_reviews


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

    @staticmethod
    def get_emoji(state, emoji_approved, emoji_commented, emoji_needs_change):
        if state == TeamState.APPROVED:
            return emoji_approved
        if state == TeamState.APPROVED_COMMENTS:
            # TODO
            return emoji_approved
        if state == TeamState.COMMENTED:
            return emoji_commented
        if state == TeamState.CHANGES_REQUESTED:
            return emoji_needs_change

        raise ValueError(f"Unknown state: {state}")


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

        # TODO
        # team_to_channel = get_team_to_channel(get_team_groups_contents())
        # channel_reviews = get_channel_reviews(reviews, team_to_channel)

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
        # timestamp = slack.find_timestamp_of_review_requested_message(pr_url=pr_url, channel_id=config.slack_channel_id)
        # print(f"Slack message timestamp: {timestamp}")

        # if timestamp is None:
        #     print(f"No message found requesting review for PR: {pr_url}")
        #     return

        # existing_emojis = slack.get_emojis_for_user(
        #     timestamp=timestamp, channel_id=config.slack_channel_id, user_id=config.slapr_bot_user_id
        # )
        # print(f"Existing emojis: {', '.join(existing_emojis)}")

        # # Review emoji
        # new_emojis = {config.emoji_review_started}
        # if review_emoji:
        #     new_emojis.add(review_emoji)

        # # PR emoji
        # print(f"Is merged: {pr.merged}")
        # print(f"Mergeable state: {pr.mergeable_state}")

        # if pr.merged:
        #     new_emojis.add(config.emoji_merged)
        # elif pr.state == "closed":
        #     new_emojis.add(config.emoji_closed)

        # # Add emojis
        # emojis_to_add, emojis_to_remove = emojis.diff(new_emojis=new_emojis, existing_emojis=existing_emojis)

        # sorted_emojis_to_add = sorted(emojis_to_add, key=config.emojis_by_review_step)

        # print(f"Emojis to add (ordered) : {', '.join(sorted_emojis_to_add)}")
        # print(f"Emojis to remove        : {', '.join(emojis_to_remove)}")

        # for review_emoji in sorted_emojis_to_add:
        #     slack.add_reaction(
        #         timestamp=timestamp,
        #         emoji=review_emoji,
        #         channel_id=config.slack_channel_id,
        #     )

        # for review_emoji in emojis_to_remove:
        #     slack.remove_reaction(
        #         timestamp=timestamp,
        #         emoji=review_emoji,
        #         channel_id=config.slack_channel_id,
        #     )
