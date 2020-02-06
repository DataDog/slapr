import json
from typing import List

from github import Github

from . import settings

gh = Github(settings.GITHUB_TOKEN)


def read_event() -> dict:
    with open(settings.GITHUB_EVENT_PATH) as f:
        return json.load(f)


def get_pr_review_states(pr_id: int) -> List[str]:
    reviews = gh.get_repo(settings.GITHUB_REPO).get_pull(pr_id).get_reviews()
    return [review.state for review in reviews]
