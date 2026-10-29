"""The things a person actually sees: a calendar feed, a one-screen week, a push.

Each reads the resolved DeadlineItems and nothing else, so the same items drive
every surface. Kept in one package because they share the small helpers for
naming an item and picking the claim that backs its date.
"""

from __future__ import annotations

from .ics import to_ics
from .push import compose, send
from .week import week_view

__all__ = ["to_ics", "week_view", "compose", "send"]


def display_name(key: str) -> str:
    """'OS:FT-II' -> 'OS FT-II'. The canonical key with the colon spelled out."""

    subject, _, rest = key.partition(":")
    return f"{subject} {rest}" if rest else key
