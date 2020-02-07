# Slapr

Add Pull Requests status emojis to Slack posts.

<img src="docs/images/example_screenshot.png"  alt="Example Screenshot" />

On `pull_request_review` or `pull_request` events Slapr will update your slack posts with suitable emojis.

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
    - uses: DataDog/hackadog-slapr@master
      env:
        GITHUB_TOKEN: "${{ secrets.GITHUB_TOKEN }}"
        GITHUB_REPO: DataDog/hackadog-slapr
        SLACK_CHANNEL_ID: CTMRQMGVB
        SLACK_API_TOKEN: "${{ secrets.SLACK_BOT_USER_OAUTH_ACCESS_TOKEN }}"
        SLAPR_BOT_USER_ID: UTMS06TPX
```
