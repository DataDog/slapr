import json
from typing import List, NamedTuple

from github import Github
from github.PullRequest import PullRequest

from . import settings

gh = Github(settings.GITHUB_TOKEN)


class Review(NamedTuple):
    state: str
    username: str


def read_event() -> dict:
    with open(settings.GITHUB_EVENT_PATH) as f:
        return json.load(f)


def get_pr_reviews(pr_number: int) -> List[Review]:
    repo = settings.GITHUB_REPO
    reviews = gh.get_repo(repo).get_pull(pr_number).get_reviews()
    return [
        Review(state=review.state.lower(), username=review.user.login)
        for review in reviews
    ]


def get_pr(pr_number: int) -> PullRequest:
    repo = settings.GITHUB_REPO
    return gh.get_repo(repo).get_pull(pr_number)
