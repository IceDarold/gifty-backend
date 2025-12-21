from __future__ import annotations

from typing import Any


def get_age_segment(age: int, ruleset: dict[str, Any]) -> str:
    segments = ruleset.get("age_segments", {})
    if not isinstance(segments, dict):
        raise ValueError("Ruleset age_segments is invalid")

    for segment, config in segments.items():
        if not isinstance(config, dict):
            continue
        age_min = config.get("age_min")
        age_max = config.get("age_max")
        if isinstance(age_min, int) and isinstance(age_max, int):
            if age_min <= age <= age_max:
                return segment

    raise ValueError(f"No age segment found for age={age}")
