"""Turn candidate messages into structured Claims.

In production this stage is Muse Glimmer: each surviving message (already
anonymised) is shown to the open-weight model, which returns the dated items it
asserts. Glimmer needs either Kaggle 2xT4 (free GGUF) or a hosted route
(Baseten), plus a card for the Meta API — none of which I can lean on while
building this week. So the pipeline talks to an `Extractor`, and a deterministic
`StubExtractor` stands in: it reads the same messages with rules and emits the
same `Claim` objects. Everything downstream — track, trust, verify, outputs, the
replay eval — is built and tested against the stub today, and swapping in
`GlimmerExtractor` changes only which extractor the pipeline constructs.

The stub is honest about its ceiling. It resolves the date forms my groups
actually use and guesses subject and kind from vocabulary, but it refuses a bare
ordinal like "11th experiment" as a calendar date, because that reading needs
real language understanding. Where the model should win — messy prose, notice
images, cross-message reasoning — is exactly where the stub returns `None`. So
the stub also serves as the "rules only" floor the eval measures Glimmer
against.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Callable, Protocol

from .schema import Claim, Message, Trust


# --- shared: who said it -> how far we trust it -----------------------------

def trust_of(sender: str) -> Trust:
    """Map an anonymised sender label to a source rank."""

    if sender.startswith("FACULTY"):
        return Trust.FACULTY
    if sender == "CR":
        return Trust.CR
    if sender == "me":
        return Trust.INFERENCE
    return Trust.RELAY          # STUDENT-xxxx or anything unpinned


class Extractor(Protocol):
    """Anything that turns messages into claims. The pipeline holds exactly one."""

    def extract(self, messages: list[Message]) -> list[Claim]: ...


# --- the deterministic stub -------------------------------------------------

# First cue wins, so the order is deliberate: a subject code anchors the item.
_SUBJECTS = {
    "OS": ("os", "operating system"),
    "DSA": ("dsa", "data structure"),
    "TBVP": ("tbvp", "transform", "boundary value"),
    "FDS": ("fds", "data science"),
    "AOOP": ("aoop", "object oriented", "object-oriented", "oops"),
}

# Checked top to bottom; "lab" sits above "exam" so "FJ lab" doesn't read as a
# written test just because the line also says "test".
_KINDS = (
    ("worksheet", ("worksheet",)),
    ("review", ("review",)),
    ("viva", ("viva",)),
    ("lab", ("lab", "experiment", "exercise", "practical", "record", "llj")),
    ("submission", ("submit", "submission", "due", "assignment", "imposition")),
    ("exam", ("ft", "ct", "llt", "cla", "fj", "exam", "test", "quiz",
              "retest", "assessment")),
)

_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}

_WEEKDAYS = {d: i for i, d in enumerate(
    ("mon", "tue", "wed", "thu", "fri", "sat", "sun"))}


def _subject_of(text: str) -> str | None:
    low = text.lower()
    for subject, cues in _SUBJECTS.items():
        if any(cue in low for cue in cues):
            return subject
    return None


def _kind_of(text: str) -> str:
    low = text.lower()
    for kind, cues in _KINDS:
        if any(re.search(rf"\b{re.escape(c)}\b", low) for c in cues):
            return kind
    return "deadline"


def _portion_of(text: str) -> str | None:
    m = re.search(r"\bunits?\s+[ivx]+(?:\s*(?:&|and|,|-|to)\s*[ivx]+)*",
                  text, re.IGNORECASE)
    return m.group(0).strip() if m else None


def _assemble(d: int, mo: int, y: str | None, ref: date, conf: float):
    """Build an ISO date from parts, filling a missing year from the message's
    own day and rolling to next year when the date would otherwise sit far in
    the past (a December message naming January means next January)."""

    year = ref.year
    if y:
        year = int(y)
        if year < 100:
            year += 2000
    try:
        cand = date(year, mo, d)
    except ValueError:
        return None, 0.4
    if not y and (cand - ref).days < -180:
        cand = date(year + 1, mo, d)
    return cand.isoformat(), conf


def _resolve_date(text: str, ref: date) -> tuple[str | None, float]:
    """Return (ISO date or None, confidence), resolving relative forms against
    `ref`, the day the message was sent."""

    low = text.lower()
    mon = "(" + "|".join(_MONTHS) + ")"

    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{mon}[a-z]*\.?"
                  rf"(?:\s*,?\s*(\d{{2,4}}))?", low)
    if m:
        return _assemble(int(m.group(1)), _MONTHS[m.group(2)], m.group(3),
                         ref, 0.9 if m.group(3) else 0.85)

    m = re.search(rf"\b{mon}[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?"
                  rf"(?:\s*,?\s*(\d{{2,4}}))?", low)
    if m:
        return _assemble(int(m.group(2)), _MONTHS[m.group(1)], m.group(3),
                         ref, 0.9 if m.group(3) else 0.85)

    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", low)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return _assemble(d, mo, m.group(3), ref, 0.9 if m.group(3) else 0.85)

    m = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday"
                  r"|mon|tue|wed|thu|fri|sat|sun)\b", low)
    if m:
        delta = (_WEEKDAYS[m.group(1)[:3]] - ref.weekday()) % 7
        return (ref + timedelta(days=delta)).isoformat(), 0.7

    if re.search(r"\b(today|tonight)\b", low):
        return ref.isoformat(), 0.7
    if re.search(r"\b(tomorrow|tmrw)\b", low):
        return (ref + timedelta(days=1)).isoformat(), 0.7

    return None, 0.4          # undated — still a real item, just unanchored


class StubExtractor:
    """Rules-only extraction: one claim per message — the first subject, the
    dominant kind, and the first date resolvable against the message's own day.
    A message with no subject anchor yields nothing."""

    def extract(self, messages: list[Message]) -> list[Claim]:
        out: list[Claim] = []
        for m in messages:
            subject = _subject_of(m.text)
            if subject is None:
                continue
            iso, conf = _resolve_date(m.text, m.ts.date())
            out.append(Claim(
                kind=_kind_of(m.text),
                subject=subject,
                date=iso,
                portion=_portion_of(m.text),
                source_msg_id=m.id,
                source_ts=m.ts,
                trust=trust_of(m.sender),
                confidence=conf,
                raw_quote=m.text.strip(),
            ))
        return out


# --- the real model, route-agnostic -----------------------------------------

_PROMPT = """You read one WhatsApp message from a university class group and \
extract every dated academic item it asserts (exams, labs, worksheets, vivas, \
reviews, submissions).

Reply with ONLY a JSON array. Each element is an object with: "kind", \
"subject", "date" (ISO YYYY-MM-DD or null if the message gives no resolvable \
date), "portion" (or null), "confidence" (0..1). If the message asserts nothing \
dated, reply [].

The message was sent on {day} by role "{sender}". Resolve relative dates \
("tomorrow", "Friday") against the day it was sent.

Message:
\"\"\"{text}\"\"\"
"""


def _first_json(raw: str) -> str:
    """Pull the first JSON array or object out of possibly chatty model output."""

    start = min((i for i in (raw.find("["), raw.find("{")) if i != -1), default=-1)
    if start == -1:
        return "[]"
    open_ch = raw[start]
    close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == open_ch:
            depth += 1
        elif raw[i] == close_ch:
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    return "[]"


class GlimmerExtractor:
    """Muse Glimmer behind one callable. `call_model(prompt) -> text` is the
    only thing that changes between the free Kaggle GGUF route and a hosted
    Baseten endpoint, so the pipeline never learns which one is live."""

    def __init__(self, call_model: Callable[[str], str]):
        self._call = call_model

    def extract(self, messages: list[Message]) -> list[Claim]:
        out: list[Claim] = []
        for m in messages:
            prompt = _PROMPT.format(
                day=m.ts.date().isoformat(), sender=m.sender, text=m.text)
            try:
                data = json.loads(_first_json(self._call(prompt)))
            except (ValueError, TypeError):
                continue                      # a bad reply drops the message, never crashes
            for obj in (data if isinstance(data, list) else [data]):
                if isinstance(obj, dict):
                    out.append(self._to_claim(obj, m))
        return out

    @staticmethod
    def _to_claim(obj: dict, m: Message) -> Claim:
        return Claim(
            kind=str(obj.get("kind") or "deadline"),
            subject=str(obj.get("subject") or _subject_of(m.text) or "?"),
            date=obj.get("date") or None,
            portion=obj.get("portion") or None,
            source_msg_id=m.id,
            source_ts=m.ts,
            trust=trust_of(m.sender),
            confidence=float(obj.get("confidence", 0.5)),
            raw_quote=m.text.strip(),
        )
