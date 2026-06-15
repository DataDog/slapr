# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

import json
from typing import List, NamedTuple

from github import Github


class Review(NamedTuple):
    state: str
    user: object  # NamedUser in production, MockUser in tests
    has_inline_comments: bool = False


class PullRequest(NamedTuple):
    state: str
    merged: bool
    mergeable_state: str


class GithubBackend:
    def read_event(self) -> dict:
        raise NotImplementedError  # pragma: no cover

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        raise NotImplementedError  # pragma: no cover

    def get_pr(self, pr_number: int) -> PullRequest:
        raise NotImplementedError  # pragma: no cover

    def get_organization(self, org: str):
        raise NotImplementedError  # pragma: no cover

    def get_user(self, username: str):
        raise NotImplementedError  # pragma: no cover

    def get_all_requested_teams(self, org_name: str, pr_number: int) -> List:
        raise NotImplementedError  # pragma: no cover


class WebGithubBackend(GithubBackend):
    def __init__(self, gh: Github, event_path: str, repo: str) -> None:
        self._gh = gh
        self.event_path = event_path
        self.repo = repo

    def read_event(self) -> dict:
        with open(self.event_path) as f:
            return json.load(f)

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        pull = self._gh.get_repo(self.repo).get_pull(pr_number)
        reviews = pull.get_reviews()
        # Fetch all review comments once and group by review ID to detect inline comments
        review_ids_with_comments = {
            comment.raw_data["pull_request_review_id"] for comment in pull.get_review_comments()
        }
        return [
            Review(
                state=review.state.lower(),
                user=review.user,
                has_inline_comments=review.id in review_ids_with_comments,
            )
            for review in reviews
        ]

    def get_pr(self, pr_number: int) -> PullRequest:
        pr = self._gh.get_repo(self.repo).get_pull(pr_number)
        return PullRequest(state=pr.state, merged=pr.merged, mergeable_state=pr.mergeable_state)

    def get_organization(self, org: str):
        return self._gh.get_organization(org)

    def get_user(self, username: str):
        return self._gh.get_user(username)

    def get_all_requested_teams(self, org_name: str, pr_number: int) -> List:
        """Get all teams ever requested for review using the Timeline API."""
        teams = {}
        pr = self._gh.get_repo(self.repo).get_pull(pr_number)
        org = self.get_organization(org_name)
        for event in pr.get_issue_events():
            if event.event == "review_requested" and "requested_team" in event.raw_data:
                slug = event.raw_data["requested_team"]["slug"]
                if slug not in teams:
                    teams[slug] = org.get_team_by_slug(slug)
        return list(teams.values())


class GithubClient:
    def __init__(self, backend: GithubBackend) -> None:
        self._backend = backend

    def read_event(self) -> dict:
        return self._backend.read_event()

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        return self._backend.get_pr_reviews(pr_number)

    def get_pr(self, pr_number: int) -> PullRequest:
        return self._backend.get_pr(pr_number)

    def get_organization(self, org: str):
        return self._backend.get_organization(org)

    def get_user(self, username: str):
        return self._backend.get_user(username)

    def get_all_requested_teams(self, org_name: str, pr_number: int) -> List:
        return self._backend.get_all_requested_teams(org_name, pr_number)
