from collections import defaultdict
import os

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


def get_team_to_channel():
    """Get a mapping team -> slack channel by reading the SLAPR_TEAM_CHANNEL_* environment variables."""

    mapping = {}
    for env, channel in os.environ.items():
        if env.startswith('SLAPR_TEAM_CHANNEL_'):
            team_name = env.removeprefix('SLAPR_TEAM_CHANNEL_').lower().replace('_', '-')
            mapping[team_name] = channel

    return mapping
