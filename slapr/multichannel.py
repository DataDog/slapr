import json
import re
from collections import defaultdict

from .github import GithubClient, get_team_state


def get_channel_reviews(reviews, team_to_channel, gh: GithubClient):
    """From the review history, deduce the review state to send to each channel."""

    # Get review for each user
    user_reviews = {}
    for review in reviews:
        # TODO: Handle approved + commented case
        user_reviews[review.username] = review.state

    # Aggregate user reviews by team
    team_reviews = defaultdict(set)
    for user, review in user_reviews.items():
        teams = gh.get_user_teams(user)
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
    """Get a mapping team -> slack channel by reading the content of the JS mapping."""

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

