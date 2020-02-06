import json
from typing import List

from github import Github

from . import settings

gh = Github(settings.GITHUB_TOKEN)


def read_event() -> dict:
    with open(settings.GITHUB_EVENT_PATH) as f:
        return json.load(f)


def get_pr_review_states(pr_number: int) -> List[str]:
    repo = settings.GITHUB_REPO
    reviews = gh.get_repo(repo).get_pull(pr_number).get_reviews()
    return [review.state.lower() for review in reviews]
