"""Render tracked deadlines as an iCalendar (.ics) feed.

Each dated item becomes an all-day VEVENT the phone's calendar can subscribe to.
Undated items carry no date, so they stay out of the feed and show up in the
week view and the push instead. The description cites the *claim that backs the
chosen date* — the faculty post, not the later rumor — so the calendar entry is
source-linked to the authority, not to whatever was said last. Text is escaped
and long lines folded per RFC 5545 so the file validates in Apple Calendar and
Google Calendar.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..schema import Claim, DeadlineItem


def _esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """Wrap to <=73 chars, continuation lines led by a space (RFC 5545)."""

    parts = []
    while len(line) > 73:
        parts.append(line[:73])
        line = " " + line[73:]
    parts.append(line)
    return "\r\n".join(parts)


def _backing_claim(item: DeadlineItem) -> Claim | None:
    """The claim whose date won — highest trust, then most recent."""

    backing = [c for c in item.history if c.date == item.current_date]
    if backing:
        return max(backing, key=lambda c: (int(c.trust), c.source_ts))
    return item.history[-1] if item.history else None


def to_ics(items: list[DeadlineItem], stamp: datetime | None = None) -> str:
    stamped = (stamp or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//hearsay//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Hearsay deadlines",
    ]
    for item in items:
        if not item.current_date:
            continue
        start = item.current_date.replace("-", "")
        end = (date.fromisoformat(item.current_date) + timedelta(days=1)
               ).isoformat().replace("-", "")
        subject, _, name = item.key.partition(":")
        summary = f"{subject} {name}".strip()

        bits: list[str] = []
        if item.portion:
            bits.append(item.portion)
        if item.flags:
            bits.append("flags: " + ", ".join(item.flags))
        source = _backing_claim(item)
        if source:
            bits.append(f"source ({source.trust.name.lower()}): {source.raw_quote}")
        description = _esc(" — ".join(bits))

        lines += [
            "BEGIN:VEVENT",
            f"UID:{item.key}@hearsay",
            f"DTSTAMP:{stamped}",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{end}",
            _fold(f"SUMMARY:{_esc(summary)}"),
            _fold(f"DESCRIPTION:{description}"),
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
