from __future__ import annotations


def subject_for_event(event_type: str, prefix: str = "analytics.events.v1") -> str:
    namespace = event_type.split(".", 1)[0] if "." in event_type else "misc"
    return f"{prefix}.{namespace}"
