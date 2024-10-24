# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

import json
from typing import List, NamedTuple, Set

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
        raise NotImplementedError  # pragma: no cover

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        raise NotImplementedError  # pragma: no cover

    def get_pr(self, pr_number: int) -> PullRequest:
        raise NotImplementedError  # pragma: no cover

    def get_user_teams(self, user: str) -> List[str]:
        raise NotImplementedError  # pragma: no cover

    def read_file(self, repo: str, path: str) -> str:
        raise NotImplementedError


class WebGithubBackend(GithubBackend):
    def __init__(self, gh: Github, event_path: str, repo: str) -> None:
        self._gh = gh
        self.event_path = event_path
        self.repo = repo
        self.gh_repo = gh.get_repo(repo)

    def read_event(self) -> dict:
        with open(self.event_path) as f:
            return json.load(f)

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        reviews = self.gh_repo.get_pull(pr_number).get_reviews()
        return [Review(state=review.state.lower(), username=review.user.login) for review in reviews]

    def get_pr(self, pr_number: int) -> PullRequest:
        pr = self.gh_repo.get_pull(pr_number)
        return PullRequest(state=pr.state, merged=pr.merged, mergeable_state=pr.mergeable_state)

    def get_user_teams(self, user: str) -> List[str]:
        """Get all the teams of a specific user."""

        import subprocess

        cmd = "gh api graphql --paginate -f query='{organization(login: \"DataDog\") {teams(first: 100, userLogins: [\"" + user + "\"]) { edges {node {name}}}}}'"
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        assert proc.returncode == 0, f'Failed to execute `{cmd}`'
        teams_json = proc.stdout
        teams_json = json.loads(teams_json)
        teams = [
            t['node']['name'] for t in teams_json['data']['organization']['teams']['edges'] if t['node']['name'] != 'Dev'
        ]

        # self._gh.get_graph

        # user = self._gh.get_user(user)
        # teams = [team.name for team in self.gh_repo.get_teams() if team.has_in_members(user) and team.name != 'Dev']

        assert len(teams) > 0, f'No team found for user {user}'

        return teams

    def read_file(self, repo, path):
        return self._gh.get_repo(repo).get_contents(path).decoded_content.decode('utf-8')


class GithubClient:
    def __init__(self, backend: GithubBackend) -> None:
        self._backend = backend

    def read_event(self) -> dict:
        return self._backend.read_event()

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        return self._backend.get_pr_reviews(pr_number)

    def get_pr(self, pr_number: int) -> PullRequest:
        return self._backend.get_pr(pr_number)

    def get_user_teams(self, user: str) -> List[str]:
        return self._backend.get_user_teams(user)

    def read_file(self, repo, path) -> str:
        return self._backend.read_file(repo, path)


class TeamState:
    APPROVED = 'approved'
    APPROVED_COMMENTS = 'approved_comments'
    COMMENTED = 'commented'
    CHANGES_REQUESTED = 'changes_requested'

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


def get_team_state(user_states: Set[str]) -> str:
    """Deduce overall team state from all reviews of multiple members of the same team."""

    if TeamState.CHANGES_REQUESTED in user_states:
        return TeamState.CHANGES_REQUESTED

    if TeamState.APPROVED in user_states:
        if TeamState.COMMENTED in user_states:
            return TeamState.APPROVED_COMMENTS
        else:
            return TeamState.APPROVED

    return TeamState.COMMENTED


def get_team_groups_contents(gh: Github) -> str:
    repo = gh.get_repo('DataDog/web-ui')
    contents = str(repo.get_contents('packages/lib/teams/teams-config.ts').decoded_content, 'utf-8')

    return contents
