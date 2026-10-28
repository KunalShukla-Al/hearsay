"""The clock the whole pipeline reads instead of the wall clock.

Replay and live differ only in which clock is injected. Replay steps a
`FakeClock` to each message's timestamp as it walks history in order; live uses
a `RealClock`. No other module calls `datetime.now()`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class RealClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock:
    """A clock pinned to a chosen instant, steppable for replay."""

    def __init__(self, at: datetime):
        self._at = at

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        self._at = at
