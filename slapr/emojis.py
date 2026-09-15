# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import List, Set, Tuple

from .approval import evaluate
from .config import Config
from .github import Review


def select(
    reviewer_teams: List,
    reviews: List[Review],
    config: Config,
    number_of_approvals_required: int,
) -> Set[str]:
    progress = evaluate(
        reviewer_teams=reviewer_teams,
        reviews=reviews,
        number_of_approvals_required=number_of_approvals_required,
    )
    return set(config.approval_rules.emojis_for(progress.state))


def diff(new_emojis: Set[str], existing_emojis: Set[str]) -> Tuple[Set[str], Set[str]]:
    emojis_to_add = new_emojis - existing_emojis
    emojis_to_remove = existing_emojis - new_emojis
    return emojis_to_add, emojis_to_remove
