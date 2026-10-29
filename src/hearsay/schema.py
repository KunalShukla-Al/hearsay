"""The types every stage of the pipeline speaks.

`Message` is the normalized unit coming out of ingest — nothing upstream of
ingest touches SQLite. `DeadlineItem` is the tracked object that `track` builds
from model output; it lives here so the whole pipeline shares one definition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class Trust(IntEnum):
    """Source rank for resolving competing claims. Higher wins."""

    INFERENCE = 0   # the agent guessed from context
    RELAY = 1       # a student forwarded or relayed something
    CR = 2          # the class representative
    FACULTY = 3     # posted or confirmed by faculty


@dataclass(frozen=True)
class Message:
    """One chat message, flattened from WhatsApp's tables.

    `ts` is a real timezone-aware UTC datetime (WhatsApp's CFAbsolute time is
    converted at ingest). `sender` is already a pseudonym once anonymize has run.
    """

    id: int
    group: str
    sender: str
    ts: datetime
    text: str
    is_from_me: bool
    media_path: str | None = None


@dataclass
class Claim:
    """A single dated item a message asserts, before tracking merges claims."""

    kind: str                 # e.g. "exam", "worksheet", "viva", "submission"
    subject: str              # e.g. "OS", "TBVP"
    date: str | None          # ISO date, or None when the message is undated
    portion: str | None
    source_msg_id: int
    source_ts: datetime       # when the claim was asserted — folds and stale-checks need it
    trust: Trust
    confidence: float         # 0..1 from the model
    raw_quote: str            # the exact line, for source-linking in outputs


@dataclass
class DeadlineItem:
    """One real-world deadline, carrying the history of what was claimed about it."""

    key: str                  # canonical id, e.g. "OS:FT-II"
    subject: str
    kind: str
    current_date: str | None
    portion: str | None
    aliases: set[str] = field(default_factory=set)   # "CT 1", "FJ2", ...
    history: list[Claim] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)    # "moved", "conflict", "stale"
    needs_question: bool = False
