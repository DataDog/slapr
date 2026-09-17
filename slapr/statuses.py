# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from typing import FrozenSet, Optional

REVIEW_STARTED = "review-started"
PARTIALLY_APPROVED = "partially-approved"
APPROVED = "approved"
CHANGES_REQUESTED = "changes-requested"
COMMENTED = "commented"
MERGED = "merged"
CLOSED = "closed"

ALL: FrozenSet[str] = frozenset(
    {REVIEW_STARTED, PARTIALLY_APPROVED, APPROVED, CHANGES_REQUESTED, COMMENTED, MERGED, CLOSED}
)


def parse_disabled(raw: Optional[str]) -> FrozenSet[str]:
    """Parse the `disabled-statuses` input: a comma-separated list of status names.

    Whitespace around each name is ignored, as are empty entries. Unknown names raise a ValueError.
    """
    if not raw:
        return frozenset()

    names = [name.strip() for name in raw.split(",")]
    names = [name for name in names if name]

    unknown = sorted(set(names) - ALL)
    if unknown:
        raise ValueError(
            f"Unknown status name(s) in disabled-statuses: {', '.join(unknown)}. "
            f"Valid names are: {', '.join(sorted(ALL))}."
        )

    return frozenset(names)
