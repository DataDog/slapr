import json
from typing import List, NamedTuple

from github import Github


class Review(NamedTuple):
    state: str
    username: str


class PullRequest(NamedTuple):
    state: str
    merged: bool
    mergeable_state: str


class GithubBackend:
    def read_event(self) -> dict:
        raise NotImplementedError

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        raise NotImplementedError

    def get_pr(self, pr_number: int) -> PullRequest:
        raise NotImplementedError


class WebGithubBackend(GithubBackend):
    def __init__(self, gh: Github, event_path: str, repo: str) -> None:
        self._gh = gh
        self.event_path = event_path
        self.repo = repo

    def read_event(self) -> dict:
        with open(self.event_path) as f:
            return json.load(f)

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        reviews = self._gh.get_repo(self.repo).get_pull(pr_number).get_reviews()
        return [Review(state=review.state.lower(), username=review.user.login) for review in reviews]

    def get_pr(self, pr_number: int) -> PullRequest:
        pr = self._gh.get_repo(self.repo).get_pull(pr_number)
        return PullRequest(state=pr.state, merged=pr.merged, mergeable_state=pr.mergeable_state)


class GithubClient:
    def __init__(self, backend: GithubBackend) -> None:
        self._backend = backend

    def read_event(self) -> dict:
        return self._backend.read_event()

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        return self._backend.get_pr_reviews(pr_number)

    def get_pr(self, pr_number: int) -> PullRequest:
        return self._backend.get_pr(pr_number)
