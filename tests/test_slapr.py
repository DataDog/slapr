from typing import List

import pytest

import slapr
from slapr.config import Config
from slapr.github import GithubBackend, GithubClient, PullRequest, Review
from slapr.slack import Message, Reaction, SlackBackend, SlackClient


class MockSlackBackend(SlackBackend):
    def __init__(self, messages: List[Message], target_message: Message, reactions: List[Reaction]) -> None:
        self.messages = messages
        self.target_message = target_message
        self.reactions = reactions
        self.emojis = [reaction.emoji for reaction in reactions]  # Retain order.

    def get_latest_messages(self, channel_id: str) -> List[Message]:
        return self.messages

    def get_reactions(self, timestamp: str, channel_id: str) -> List[Reaction]:
        return list(self.reactions)

    def add_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        assert timestamp == self.target_message.timestamp
        if emoji in self.emojis:
            raise RuntimeError(f"Emoji already present: {emoji!r}")  # Mimick behavior of real Slack.
        self.emojis.append(emoji)

    def remove_reaction(self, timestamp: str, emoji: str, channel_id: str) -> None:
        assert timestamp == self.target_message.timestamp
        if emoji not in self.emojis:
            return  # Mimick behavior of real Slack.
        self.emojis.remove(emoji)


class MockGithubBackend(GithubBackend):
    def __init__(self, reviews: List[Review], event: dict, pr: PullRequest) -> None:
        self.reviews = reviews
        self.event = event
        self.pr = pr

    def read_event(self) -> dict:
        return self.event

    def get_pr(self, pr_number: int) -> PullRequest:
        assert pr_number == self.event["pull_request"]["number"]
        return self.pr

    def get_pr_reviews(self, pr_number: int) -> List[Review]:
        assert pr_number == self.event["pull_request"]["number"]
        return list(self.reviews)


MOCK_EVENT = {
    "pull_request": {
        "number": 42,
        "html_url": "https://github.com/example/repo/pull/42",
        "head": {
            "repo": {
                "fork": False
            }
        }
    }
}


@pytest.mark.parametrize(
    "messages, reviews, reactions, expected_emojis",
    [
        pytest.param(
            [Message(text="Need review <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="approved", username="alice")],
            [],
            ["test_review_started", "test_approved"],
            id="approval",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="changes_requested", username="alice")],
            [],
            ["test_review_started", "test_needs_change"],
            id="changes_requested",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="comment", username="alice")],
            [],
            ["test_review_started"],
            id="comment",
        ),
        pytest.param(
            [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")],
            [Review(state="changes_requested", username="alice"), Review(state="approved", username="alice")],
            [Reaction(emoji="test_needs_change", user_ids=["U1234"])],
            ["test_review_started", "test_approved"],
            id="approved-from-changes-requested",
        ),
        pytest.param(
            [Message(text="Need :eyes: but I've got no PR URL", timestamp="yyyy-mm-dd")],
            [Review(state="approved", username="alice")],
            [],
            [],
            id="message-not-found",
        ),
    ],
)
def test_on_pull_request_review(
    messages: List[Message], reviews: List[Review], reactions: List[Reaction], expected_emojis: set
) -> None:
    slack_backend = MockSlackBackend(messages=messages, target_message=messages[0], reactions=reactions)
    github_backend = MockGithubBackend(
        reviews=reviews,
        event=MOCK_EVENT,
        pr=PullRequest(state="open", merged=False, mergeable_state="clean"),
    )

    config = Config(
        slack_client=SlackClient(backend=slack_backend),
        github_client=GithubClient(backend=github_backend),
        slack_channel_id="C1234",
        slapr_bot_user_id="U1234",
        number_of_approvals_required=1,
        emoji_review_started="test_review_started",
        emoji_approved="test_approved",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
    )
    slapr.main(config)

    assert slack_backend.emojis == expected_emojis


@pytest.mark.parametrize(
    "event, pr, reactions, expected_emojis",
    [
        pytest.param(
            MOCK_EVENT,
            PullRequest(state="closed", merged=True, mergeable_state="clean"),
            [
                Reaction(emoji="test_review_started", user_ids=["U1234"]),
                Reaction(emoji="test_approved", user_ids=["U1234"]),
            ],
            ["test_review_started", "test_approved", "test_merged"],
            id="merge-approved-pr",
        ),
        pytest.param(
            MOCK_EVENT,
            PullRequest(state="closed", merged=False, mergeable_state="clean"),
            [
                Reaction(emoji="test_review_started", user_ids=["U1234"]),
                Reaction(emoji="test_approved", user_ids=["U1234"]),
            ],
            ["test_review_started", "test_approved", "test_closed"],
            id="merge-approved-pr",
        ),
    ],
)
def test_on_pull_request(event: dict, pr: PullRequest, reactions: List[Reaction], expected_emojis: set) -> None:
    messages = [Message(text="Need :eyes: <https://github.com/example/repo/pull/42>", timestamp="yyyy-mm-dd")]
    reviews = [Review(state="approved", username="alice")]

    slack_backend = MockSlackBackend(messages=messages, target_message=messages[0], reactions=reactions)
    github_backend = MockGithubBackend(reviews=reviews, event=event, pr=pr,)

    config = Config(
        slack_client=SlackClient(backend=slack_backend),
        github_client=GithubClient(backend=github_backend),
        slack_channel_id="C1234",
        slapr_bot_user_id="U1234",
        number_of_approvals_required=1,
        emoji_review_started="test_review_started",
        emoji_approved="test_approved",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
    )
    slapr.main(config)

    assert slack_backend.emojis == expected_emojis
