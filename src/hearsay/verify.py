"""Flag what a human should double-check, and draft the question to send.

Runs after `trust.resolve` has chosen `current_date`. It raises three flags:

  - **moved**: the winning authority itself asserted more than one date over
    time — a genuine reschedule (current_date already holds the latest);
  - **conflict**: a claim from a different rank disagrees with the chosen date —
    a rumor or a cross-group contradiction, surfaced even when trust settles it;
  - **stale**: the chosen date is still upcoming but nothing has confirmed it in
    a while, so it is worth re-checking.

It sets `needs_question` (and drafts `question`) only when the agent is
genuinely unsure: an undated item, or a disagreement with no faculty backing. A
rumor that faculty already overrules is flagged but asks nothing — the whole
point is to not nag when the source rank already decides it.
"""

from __future__ import annotations

from datetime import date

from .schema import DeadlineItem, Trust

_SAID = {
    Trust.FACULTY: "faculty",
    Trust.CR: "CR",
    Trust.RELAY: "a classmate",
    Trust.INFERENCE: "a guess",
}


def _name(item: DeadlineItem) -> str:
    return item.key.split(":", 1)[1]


def _draft(item: DeadlineItem) -> str:
    dated = sorted((c for c in item.history if c.date), key=lambda c: c.source_ts)
    if not dated:
        quote = item.history[0].raw_quote if item.history else ""
        return f'{item.subject} {_name(item)}: no date found in "{quote}". When is it due?'
    opts = " vs ".join(
        f"{c.date} ({_SAID[c.trust]}, {c.source_ts.date().isoformat()})" for c in dated)
    return f"{item.subject} {_name(item)}: I have {opts}. Which is correct?"


def verify(item: DeadlineItem, today: date, stale_days: int = 14) -> DeadlineItem:
    dated = [c for c in item.history if c.date]
    flags: list[str] = []

    if dated:
        top = max(int(c.trust) for c in dated)
        if len({c.date for c in dated if int(c.trust) == top}) > 1:
            flags.append("moved")
        if any(c.date != item.current_date for c in dated):
            flags.append("conflict")

    newest = max((c.source_ts for c in item.history), default=None)
    if (item.current_date and item.current_date >= today.isoformat()
            and newest and (today - newest.date()).days > stale_days):
        flags.append("stale")

    item.flags = flags

    faculty_backs = any(
        c.trust is Trust.FACULTY and c.date == item.current_date for c in dated)
    unsure = (not dated) or ("conflict" in flags and not faculty_backs)
    item.needs_question = unsure
    item.question = _draft(item) if unsure else None
    return item


def adjudicate(items: list[DeadlineItem], today: date,
               stale_days: int = 14) -> list[DeadlineItem]:
    """Resolve the date and run the verifier on every item, in place."""

    from .trust import resolve

    for item in items:
        resolve(item)
        verify(item, today, stale_days)
    return items
