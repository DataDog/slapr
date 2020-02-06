import json

from . import settings


def read_event() -> dict:
    with open(settings.GITHUB_EVENT_PATH) as f:
        return json.load(f)
