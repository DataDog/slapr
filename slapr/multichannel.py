import json
import sys
from collections import defaultdict

from .github import GithubClient, get_team_state


def get_channel_reviews(reviews, team_to_channel, gh: GithubClient):
    """From the review history, deduce the review state to send to each channel."""

    # Get review for each user
    user_reviews = {}
    for review in reviews:
        user_reviews[review.username] = review.state

    # Aggregate user reviews by team
    team_reviews = defaultdict(set)
    for user, review in user_reviews.items():
        try:
            teams = gh.get_user_teams(user)
            print(f"User: {user}, Review: {review}, Teams: {teams}")
            for team in teams:
                team_reviews[team].add(review)
        except Exception:
            print(f"Warning: Could not get teams for user {user}", file=sys.stderr)

    # Aggregate team reviews by channel
    channel_reviews = defaultdict(set)
    for team, reviews in team_reviews.items():
        print(f'Team: {team}, Reviews: {reviews}')

        if team not in team_to_channel:
            print(f'Warning: No slack channel for team {team}', file=sys.stderr)
            continue

        channel = team_to_channel[team]
        channel_reviews[channel].update(reviews)

    # Get overall state for each channel
    channel_reviews = {channel: get_team_state(reviews) for channel, reviews in channel_reviews.items()}

    return channel_reviews


def get_team_to_channel(team_mapping_file):
    """Get a mapping team -> slack channel by reading the SLAPR_TEAM_CHANNEL_* environment variables."""

    with open(team_mapping_file) as f:
        team_to_channel = json.load(f)

    assert len(team_to_channel) > 0, 'Team mapping file is empty.'

    return team_to_channel
