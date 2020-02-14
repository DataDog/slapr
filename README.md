# Slapr

Add Pull Requests status emojis to Slack posts.

<img src="docs/images/example_screenshot.png"  alt="Example Screenshot" />

On `pull_request_review` or `pull_request` events Slapr will update your slack posts with suitable emojis.

Slack posts should match this pattern:

`:eyes:` or `rev` followed by a `space` and the PR URL

`(:eyes:|rev)\s+<PR_URL>`

Examples:

- Blabla Need Review for :eyes: https://github.com/DataDog/integrations-core/pull/5746/s
- Blabla Need Review for rev https://github.com/DataDog/integrations-core/pull/5746/s

Note: There is a [pending PR](https://github.com/DataDog/slapr/issues/21) to make this pattern configurable 

## Requirements

Slack API Token with following permissions

- `channels:history`
- `reactions:read`
- `reactions:write`

## Emoji status

| emoji | description |
| ----- | ----------- |
|`EMOJI_REVIEW_STARTED`|The PR has at least one review has been made.|
|`EMOJI_APPROVED`|The PR is approved and ready to be merged.|
|`EMOJI_NEEDS_CHANGES`|Changes are requested for the PR.|
|`EMOJI_MERGED`|The PR is merged.|
|`EMOJI_CLOSED`|The PR is closed.|

## Example Usage

```yaml
name: Slack emoji PR updates
on:
  pull_request_review:
    types: [submitted]
  pull_request:
    types: [closed]

jobs:
  run_slapr:
    runs-on: ubuntu-latest
    steps:
    - uses: DataDog/slapr@master
      env:
        GITHUB_TOKEN: "${{ secrets.GITHUB_TOKEN }}"
        GITHUB_REPO: DataDog/slapr
        SLACK_CHANNEL_ID: CTMRQMGVB
        SLACK_API_TOKEN: "${{ secrets.SLACK_BOT_USER_OAUTH_ACCESS_TOKEN }}"
        SLAPR_BOT_USER_ID: UTMS06TPX
```
