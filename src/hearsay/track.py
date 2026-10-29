"""Merge claims into one tracked DeadlineItem per real deadline.

One deadline is named many ways across groups — "OS FT-II", "CT 1" and "FJ2" are
the same test. Two things link claims into one item:

  1. a shared instance alias (FT-II, CT-1, FJ-II, LLT-I, CLA-T1, ...), including
     aliases that co-occur in a single message like "OS FT-II (FJ2)"; and
  2. failing an alias, a bare "<subject> <kind>" claim ("OS test moved to 30
     Oct") attaches to the one open item of that subject and kind.

Claims are folded in the order they were asserted, so an item already exists
before a later, vaguer message tries to join it. This step only *groups* claims
and records their history and aliases. Choosing the winning date among
conflicting claims, and raising the moved / conflict / stale flags, is the
trust+verify step (Day 4). Until then `current_date` is the most recently
asserted dated claim — best effort, deliberately naive.
"""

from __future__ import annotations

import re

from .schema import Claim, DeadlineItem

# An assessment-instance code: a prefix plus an arabic or roman numeral.
_ALIAS_RE = re.compile(
    r"\b(ft|ct|llt|llj|fj|cla-?t|cla)\s*[-\s]?\s*(\d{1,2}|iv|v?i{1,3}|v)\b",
    re.IGNORECASE,
)

_PREFIX = {"ft": "FT", "ct": "CT", "llt": "LLT", "llj": "LLJ", "fj": "FJ",
           "cla": "CLA-T", "clat": "CLA-T", "cla-t": "CLA-T"}

# Written tests name the item before lab-side names do, so "FT-II" wins "FJ-II"
# as the canonical key for the same test.
_PRIMARY_ORDER = ("FT", "CT", "LLT", "CLA-T", "LLJ", "FJ")

_ARABIC_TO_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
                    6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}


def _roman(numeral: str) -> str:
    numeral = numeral.strip().upper()
    if numeral.isdigit():
        return _ARABIC_TO_ROMAN.get(int(numeral), numeral)
    return numeral


def aliases_in(text: str) -> set[str]:
    """Every instance code in a line, normalised to 'PREFIX-ROMAN'."""

    out = set()
    for prefix, numeral in _ALIAS_RE.findall(text):
        out.add(f"{_PREFIX[prefix.lower()]}-{_roman(numeral)}")
    return out


def _primary(aliases: set[str]) -> str | None:
    for pref in _PRIMARY_ORDER:
        hits = sorted(a for a in aliases if a.startswith(pref + "-"))
        if hits:
            return hits[0]
    return sorted(aliases)[0] if aliases else None


def _key(subject: str, aliases: set[str], kind: str) -> str:
    primary = _primary(aliases)
    return f"{subject}:{primary}" if primary else f"{subject}:{kind}"


class _Item:
    """Mutable accumulator; frozen into a DeadlineItem at the end."""

    def __init__(self, subject: str, kind: str):
        self.subject = subject
        self.kind = kind
        self.aliases: set[str] = set()
        self.history: list[Claim] = []

    def add(self, claim: Claim, aliases: set[str]) -> None:
        self.history.append(claim)
        self.aliases |= aliases

    def finish(self) -> DeadlineItem:
        dated = [c for c in self.history if c.date]
        latest = max(dated, key=lambda c: c.source_ts, default=None)
        portioned = [c for c in self.history if c.portion]
        return DeadlineItem(
            key=_key(self.subject, self.aliases, self.kind),
            subject=self.subject,
            kind=self.kind,
            current_date=latest.date if latest else None,
            portion=(max(portioned, key=lambda c: c.source_ts).portion
                     if portioned else None),
            aliases=set(self.aliases),
            history=list(self.history),
        )


def track(claims: list[Claim]) -> list[DeadlineItem]:
    """Group claims into deadline items, linking aliases across messages."""

    items: list[_Item] = []

    for claim in sorted(claims, key=lambda c: c.source_ts):
        al = aliases_in(claim.raw_quote)

        if al:
            matches = [it for it in items
                       if it.subject == claim.subject and it.aliases & al]
            if matches:
                target = matches[0]
                for extra in matches[1:]:          # a bridging claim merges items
                    target.aliases |= extra.aliases
                    target.history += extra.history
                    items.remove(extra)
            else:
                target = _Item(claim.subject, claim.kind)
                items.append(target)
            target.add(claim, al)
            continue

        # No alias: attach to the one open item of this subject+kind, else start one.
        same = [it for it in items
                if it.subject == claim.subject and it.kind == claim.kind]
        target = same[0] if len(same) == 1 else _Item(claim.subject, claim.kind)
        if target not in items:
            items.append(target)
        target.add(claim, al)

    return [it.finish() for it in items]
