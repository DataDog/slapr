from slapr.config import Config
from slapr.emojis import sort_emojis
from slapr.github import GithubClient, GithubBackend
from slapr.slack import SlackClient, SlackBackend


def test_sort_emojis():
    config = Config(
        slack_client=SlackClient(backend=SlackBackend()),
        github_client=GithubClient(backend=GithubBackend()),
        slack_channel_id="C1234",
        slapr_bot_user_id="U1234",
        emoji_review_started="test_review_started",
        emoji_approved="test_approved",
        emoji_needs_change="test_needs_change",
        emoji_merged="test_merged",
        emoji_closed="test_closed",
    )

    emojis = {"test_approved", "test_needs_change", "test_merged", "test_review_started", "test_closed"}

    ordered_emojis = sort_emojis(config, emojis)

    assert ordered_emojis == ['test_review_started',
                              'test_needs_change',
                              'test_approved',
                              'test_closed',
                              'test_merged',
                              ]
