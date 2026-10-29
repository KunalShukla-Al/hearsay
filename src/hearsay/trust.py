"""Pick the authoritative date for a tracked item.

Competing claims are ranked FACULTY > CR > RELAY > INFERENCE, and within one
rank the most recently asserted wins. So a faculty post beats a student rumor
however recent the rumor, and a later faculty correction beats an earlier
faculty post. This never *drops* the losing claims — they stay in history for
`verify` to flag — it only chooses what the item currently reads.
"""

from __future__ import annotations

from .schema import DeadlineItem


def _rank(claim):
    return (int(claim.trust), claim.source_ts)


def resolve(item: DeadlineItem) -> DeadlineItem:
    """Set current_date and portion from the most authoritative, then most
    recent, claim that carries one."""

    dated = [c for c in item.history if c.date]
    item.current_date = max(dated, key=_rank).date if dated else None

    portioned = [c for c in item.history if c.portion]
    if portioned:
        item.portion = max(portioned, key=_rank).portion
    return item
