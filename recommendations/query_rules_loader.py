from __future__ import annotations

from typing import Any

import yaml


def load_ruleset(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"Ruleset file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Ruleset YAML is invalid: {path}") from exc

    if not isinstance(data, dict):
        raise ValueError("Ruleset must be a mapping at top level")

    for key in ("version", "age_segments", "limits"):
        if key not in data:
            raise ValueError(f"Ruleset missing required key: {key}")

    return data
