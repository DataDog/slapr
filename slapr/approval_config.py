# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

from .approval import ApprovalState


STATE_DISPLAY_ORDER = (
    ApprovalState.NONE,
    ApprovalState.COMMENTED,
    ApprovalState.BLOCKED,
    ApprovalState.PARTIAL,
    ApprovalState.COMPLETE,
    ApprovalState.UNKNOWN,
)


class ApprovalConfig:
    def __init__(self, emojis_by_state: Mapping[ApprovalState, Sequence[str]]) -> None:
        self._emojis_by_state: Dict[ApprovalState, Tuple[str, ...]] = {
            state: tuple(emojis_by_state.get(state, ())) for state in ApprovalState
        }

    @classmethod
    def load(cls, file_path: str) -> "ApprovalConfig":
        with open(file_path, encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)

        if not isinstance(raw_config, dict):
            raise ValueError("approval config must be a mapping")

        unknown_keys = [key for key in raw_config if key not in {"version", "states"}]
        if unknown_keys:
            formatted_keys = ", ".join(sorted(str(key) for key in unknown_keys))
            raise ValueError(f"unknown approval config keys: {formatted_keys}")

        if raw_config.get("version") != 1:
            raise ValueError("approval config version must be 1")

        raw_states = raw_config.get("states")
        if not isinstance(raw_states, dict):
            raise ValueError("approval config states must be a mapping")

        supported_states = {state.value for state in ApprovalState}
        unknown_states = [state for state in raw_states if not isinstance(state, str) or state not in supported_states]
        if unknown_states:
            formatted_states = ", ".join(sorted(str(state) for state in unknown_states))
            raise ValueError(f"unknown approval states: {formatted_states}")

        emojis_by_state: Dict[ApprovalState, List[str]] = {}
        state_by_emoji: Dict[str, ApprovalState] = {}
        for state_name, raw_emojis in raw_states.items():
            if not isinstance(raw_emojis, list):
                raise ValueError(f"approval state {state_name!r} must contain a list of emoji names")

            state = ApprovalState(state_name)
            emojis: List[str] = []
            for raw_emoji in raw_emojis:
                if not isinstance(raw_emoji, str) or not raw_emoji.strip() or raw_emoji != raw_emoji.strip():
                    raise ValueError(f"approval state {state_name!r} contains an invalid emoji name")
                if raw_emoji in emojis:
                    raise ValueError(f"approval state {state_name!r} contains duplicate emoji {raw_emoji!r}")
                if raw_emoji in state_by_emoji:
                    other_state = state_by_emoji[raw_emoji]
                    raise ValueError(
                        f"emoji {raw_emoji!r} is assigned to both {other_state.value!r} and {state_name!r}"
                    )
                emojis.append(raw_emoji)
                state_by_emoji[raw_emoji] = state
            emojis_by_state[state] = emojis

        return cls(emojis_by_state)

    @classmethod
    def from_legacy(
        cls,
        emoji_commented: str,
        emoji_needs_change: str,
        emoji_partially_approved: Optional[str],
        emoji_approved: str,
    ) -> "ApprovalConfig":
        emojis_by_state = {
            ApprovalState.COMMENTED: [emoji_commented],
            ApprovalState.BLOCKED: [emoji_needs_change],
            ApprovalState.COMPLETE: [emoji_approved],
        }
        if emoji_partially_approved:
            emojis_by_state[ApprovalState.PARTIAL] = [emoji_partially_approved]
        return cls(emojis_by_state)

    def emojis_for(self, state: ApprovalState) -> Tuple[str, ...]:
        return self._emojis_by_state[state]

    @property
    def ordered_emojis(self) -> Tuple[str, ...]:
        return tuple(emoji for state in STATE_DISPLAY_ORDER for emoji in self._emojis_by_state[state])
