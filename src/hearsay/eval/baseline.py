"""The thing the agent has to beat: "latest message wins".

A naive reader with no notion of who said what — it takes the most recently
asserted date for each tracked item and stops there. No source rank, so a
student's later rumour overwrites a faculty announcement; no verify, so nothing
is flagged and nothing is ever questioned. It shares `track`'s alias-linking, so
the only thing separating it from the agent is trust and verification — which is
exactly what the eval is there to measure.
"""

from __future__ import annotations

from ..schema import DeadlineItem


def latest_wins(items: list[DeadlineItem]) -> list[DeadlineItem]:
    """Set each item's date to its most recently asserted dated claim, in place."""

    for item in items:
        dated = [c for c in item.history if c.date]
        item.current_date = max(dated, key=lambda c: c.source_ts).date if dated else None
        item.flags = []
        item.needs_question = False
        item.question = None
    return items
