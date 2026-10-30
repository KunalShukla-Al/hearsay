"""Replay the term message by message and score each day against the log.

The one idea the project is built on: replay and live are the same pipeline on
different clocks. `agent_view` and `baseline_view` both take an `instant`, set a
`FakeClock` to it, and reason over only the messages known by then — so "what
would the agent have told me on 21 Oct?" is just the clock sitting at 21 Oct.
`replay` runs that at every date a message arrives and scores the agent (trust +
verify) and the `latest_wins` baseline against a hand-checked ground-truth log.

Ground truth is a Markdown table of `key | date | portion`. The committed one,
`tests/fixtures/ground_truth.md`, covers the synthetic fixture so the eval runs
today with no private data; the real term log lives at
`private/Deadlines_till_20_Nov_2026.md` (git-ignored) in the same shape and is
passed with --truth.

Run it:  PYTHONPATH=src python -m hearsay.eval.replay
         PYTHONPATH=src python -m hearsay.eval.replay --db private/chat.sqlite \
             --truth private/Deadlines_till_20_Nov_2026.md --roster private/roster.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from ..anonymize import anonymize
from ..clock import FakeClock
from ..ingest import read_messages
from ..model import StubExtractor
from ..prefilter import prefilter
from ..schema import DeadlineItem, Message
from ..track import track
from ..verify import adjudicate
from .baseline import latest_wins

_UNDATED = {"", "none", "-", "undated", "n/a"}


@dataclass(frozen=True)
class Truth:
    """One hand-checked deadline: the correct date (or None) and portion."""

    date: str | None
    portion: str | None = None


def parse_truth(text: str) -> dict[str, Truth]:
    """Read a `key | date | portion` Markdown table into {key: Truth}."""

    out: dict[str, Truth] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        key, raw_date = cells[0], cells[1]
        if key.lower() == "key" or set(key) <= {"-"}:
            continue                                   # header or separator row
        portion = cells[2] if len(cells) > 2 and cells[2] else None
        when = None if raw_date.lower() in _UNDATED else raw_date
        out[key] = Truth(date=when, portion=portion)
    return out


def _known(messages: list[Message], instant: datetime) -> list[Message]:
    clock = FakeClock(instant)
    return [m for m in messages if m.ts <= clock.now()]


def agent_view(messages: list[Message], instant: datetime, extractor=None) -> dict[str, DeadlineItem]:
    """The full pipeline (track -> trust -> verify) over messages known by `instant`."""

    extractor = extractor or StubExtractor()
    items = track(extractor.extract(_known(messages, instant)))
    return {it.key: it for it in adjudicate(items, instant.date())}


def baseline_view(messages: list[Message], instant: datetime, extractor=None) -> dict[str, DeadlineItem]:
    """"Latest message wins" over the same known messages — no trust, no verify."""

    extractor = extractor or StubExtractor()
    items = latest_wins(track(extractor.extract(_known(messages, instant))))
    return {it.key: it for it in items}


@dataclass
class Score:
    """How one view (agent or baseline) did against the log at one as-of date."""

    as_of: date
    n_truth: int
    surfaced: int                           # real deadlines the view found
    spurious: int                           # keys the view invented
    date_total: int                         # surfaced truth items that have a date
    date_correct: int                       # ... the view dated correctly
    undated_total: int                      # surfaced truth items with no date
    undated_correct: int                    # ... the view also left undated
    wrong: list[str] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return self.surfaced / self.n_truth if self.n_truth else 1.0

    @property
    def precision(self) -> float:
        found = self.surfaced + self.spurious
        return self.surfaced / found if found else 1.0

    @property
    def date_accuracy(self) -> float:
        return self.date_correct / self.date_total if self.date_total else 1.0


def score(view: dict[str, DeadlineItem], truth: dict[str, Truth], as_of: date) -> Score:
    """Compare a view to the log: recall/precision on items, accuracy on dates."""

    hits = sorted(set(view) & set(truth))
    spurious = len(set(view) - set(truth))
    s = Score(as_of=as_of, n_truth=len(truth), surfaced=len(hits), spurious=spurious,
              date_total=0, date_correct=0, undated_total=0, undated_correct=0)
    for key in hits:
        want = truth[key].date
        got = view[key].current_date
        if want is None:
            s.undated_total += 1
            if got is None:
                s.undated_correct += 1
            else:
                s.wrong.append(f"{key}: {got} (expected undated)")
        else:
            s.date_total += 1
            if got == want:
                s.date_correct += 1
            else:
                s.wrong.append(f"{key}: {got or 'none'} != {want}")
    return s


def replay(messages: list[Message], truth: dict[str, Truth], extractor=None,
           dates: list[date] | None = None) -> list[tuple[date, Score, Score]]:
    """Score the agent and the baseline at each date a message arrives."""

    extractor = extractor or StubExtractor()
    dates = dates or sorted({m.ts.date() for m in messages})
    rows = []
    for day in dates:
        instant = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
        agent = score(agent_view(messages, instant, extractor), truth, day)
        base = score(baseline_view(messages, instant, extractor), truth, day)
        rows.append((day, agent, base))
    return rows


# --- CLI --------------------------------------------------------------------

def _repo_file(*parts: str) -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", "..", *parts)


def _load_messages(db: str | None, roster_path: str | None) -> list[Message]:
    db = db or _repo_file("tests", "fixtures", "chat.sqlite")
    if roster_path:
        with open(roster_path, encoding="utf-8") as fh:
            roster = json.load(fh)
    else:
        roster = {"Dr Wilson": "FACULTY-OS", "Anmol CR": "CR"}   # the fixture's cast
    return prefilter(anonymize(read_messages(db), roster=roster))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay the term and score agent vs baseline.")
    ap.add_argument("--db", help="WhatsApp DB copy (default: the test fixture)")
    ap.add_argument("--truth", help="ground-truth Markdown (default: the fixture log)")
    ap.add_argument("--roster", help="JSON {real name: role} for anonymize (real data)")
    args = ap.parse_args(argv)

    messages = _load_messages(args.db, args.roster)
    truth_path = args.truth or _repo_file("tests", "fixtures", "ground_truth.md")
    with open(truth_path, encoding="utf-8") as fh:
        truth = parse_truth(fh.read())

    rows = replay(messages, truth)
    label = "fixture" if not args.db else os.path.basename(args.db)
    print(f"Hearsay replay — {label} ({len(messages)} messages, {len(truth)} deadlines)\n")
    print(f"{'as-of':<12}{'agent dates':<14}{'baseline dates':<16}divergence")
    for day, agent, base in rows:
        diff = "; ".join(agent.wrong + base.wrong) or "-"
        print(f"{day.isoformat():<12}{_frac(agent):<14}{_frac(base):<16}{diff}")

    _, agent, base = rows[-1]
    print(f"\nFinal {rows[-1][0].isoformat()}: recall {agent.surfaced}/{agent.n_truth}, "
          f"precision {agent.surfaced}/{agent.surfaced + agent.spurious}")
    print(f"  agent    date accuracy {agent.date_correct}/{agent.date_total}"
          f"  (+{agent.undated_correct}/{agent.undated_total} undated held)")
    print(f"  baseline date accuracy {base.date_correct}/{base.date_total}")
    if agent.date_accuracy > base.date_accuracy:
        print("\nThe later rumour flips the baseline; trust keeps the agent on the faculty date.")
    return 0


def _frac(s: Score) -> str:
    return f"{s.date_correct}/{s.date_total}+{s.undated_correct}u"


if __name__ == "__main__":
    sys.exit(main())
