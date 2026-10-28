"""Keep only messages that could carry a date or an assessment.

The model is the expensive step, so it should never see pure chatter. A message
survives if it mentions a date/time cue or an assessment word. This is a cheap,
deliberately generous net — recall matters more than precision here, since a
dropped message can never be recovered downstream, while a false keep only costs
one model look.
"""

from __future__ import annotations

import re

from .schema import Message

# Assessment vocabulary from my own groups: cycle/formative tests, lab jobs,
# life-long tests, vivas, worksheets, submissions, reviews.
_ASSESS = re.compile(
    r"\b(ft|ct|llt|llj|fj|cla|exam|test|quiz|viva|lab|worksheet|assignment"
    r"|submit|submission|due|deadline|portion|syllabus|review|imposition"
    r"|retest|assessment|practical|record|experiment|exercise|ex)\b",
    re.IGNORECASE,
)

# Date/time cues: explicit dates, weekdays, months, day-orders, times, relatives.
_DATE = re.compile(
    r"(\d{1,2}[/.-]\d{1,2}([/.-]\d{2,4})?"
    r"|\b\d{1,2}\s?(st|nd|rd|th)?\s?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"|\b\d{1,2}(st|nd|rd|th)\b"
    r"|\b(mon|tue|wed|thu|fri|sat|sun)(day)?\b"
    r"|\bday\s?order\s?\d|\bdo\s?\d"
    r"|\b\d{1,2}[:.]\d{2}\s?(am|pm)?\b"
    r"|\b(today|tomorrow|tmrw|tonight|next week|this week|asap)\b)",
    re.IGNORECASE,
)


def is_candidate(text: str) -> bool:
    return bool(_ASSESS.search(text) and _DATE.search(text)) or bool(
        # a bare assessment word with "📣"-style urgency still worth a look
        _ASSESS.search(text) and re.search(r"[!📣⚠️🆕🔁]", text)
    )


def prefilter(messages: list[Message]) -> list[Message]:
    """Return the subset of messages worth sending to the model."""

    return [m for m in messages if m.text and is_candidate(m.text)]
