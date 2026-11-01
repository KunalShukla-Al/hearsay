"""The live product: the same pipeline as the replay eval, on a real clock.

`pipeline` is the one composition both sides share — extract, track, then trust
and verify. The replay eval (hearsay.eval.replay) runs it at a `FakeClock`
instant over the messages known by then; here it runs at `RealClock` now over
the whole chat and feeds the three output surfaces. That is the blueprint's one
idea made literal: replay and live differ only in which clock is injected.

Run it:
  PYTHONPATH=src python -m hearsay.run                       # this week's view (fixture)
  PYTHONPATH=src python -m hearsay.run --out ics             # the calendar feed
  PYTHONPATH=src python -m hearsay.run --as-of 2026-10-28    # show what I'd have seen that day
  PYTHONPATH=src python -m hearsay.run --db private/chat.sqlite --roster private/roster.json --out push
  GLIMMER_BASE_URL=... GLIMMER_MODEL=... python -m hearsay.run --model glimmer   # the real model
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone

from .anonymize import anonymize
from .clock import Clock, FakeClock, RealClock
from .ingest import read_messages
from .model import GlimmerExtractor, StubExtractor
from .outputs import compose, send, to_ics, week_view
from .route import glimmer_route
from .prefilter import prefilter
from .schema import DeadlineItem, Message
from .track import track
from .verify import adjudicate


def pipeline(messages: list[Message], today: date, extractor=None) -> list[DeadlineItem]:
    """Messages -> resolved deadline items: extract, track, then trust + verify."""

    extractor = extractor or StubExtractor()
    return adjudicate(track(extractor.extract(messages)), today)


def _repo_file(*parts: str) -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", *parts)


def load_messages(db: str | None = None, roster_path: str | None = None) -> list[Message]:
    """Ingest -> anonymize -> prefilter, from the fixture by default."""

    db = db or _repo_file("tests", "fixtures", "chat.sqlite")
    if roster_path:
        with open(roster_path, encoding="utf-8") as fh:
            roster = json.load(fh)
    else:
        roster = {"Dr Wilson": "FACULTY-OS", "Anmol CR": "CR"}   # the fixture's cast
    return prefilter(anonymize(read_messages(db), roster=roster))


def _ntfy_topic(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    try:
        with open(os.path.expanduser("~/.config/noticeagent/ntfy-topic"), encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the live notice pipeline.")
    ap.add_argument("--db", help="WhatsApp DB copy (default: the test fixture)")
    ap.add_argument("--roster", help="JSON {real name: role} for anonymize (real data)")
    ap.add_argument("--out", choices=["week", "ics", "push"], default="week")
    ap.add_argument("--model", choices=["stub", "glimmer"], default="stub",
                    help="glimmer uses the live route (GLIMMER_BASE_URL, GLIMMER_MODEL)")
    ap.add_argument("--ntfy-topic", help="ntfy topic for --out push")
    ap.add_argument("--as-of", help="pin the clock to an ISO datetime (replay-style) instead of now")
    args = ap.parse_args(argv)

    clock: Clock = RealClock()
    if args.as_of:
        at = datetime.fromisoformat(args.as_of)
        clock = FakeClock(at if at.tzinfo else at.replace(tzinfo=timezone.utc))
    today = clock.now().date()

    messages = load_messages(args.db, args.roster)
    if args.as_of:
        messages = [m for m in messages if m.ts <= clock.now()]   # only what was known by then
    extractor = GlimmerExtractor(glimmer_route()) if args.model == "glimmer" else None
    items = pipeline(messages, today, extractor)

    if args.out == "week":
        print(week_view(items, today))
    elif args.out == "ics":
        print(to_ics(items))
    else:
        topic = _ntfy_topic(args.ntfy_topic)
        if not topic:
            print("No ntfy topic: pass --ntfy-topic or write ~/.config/noticeagent/ntfy-topic.", file=sys.stderr)
            return 1
        status = send(items, today, topic=topic)
        title, _ = compose(items, today)
        print(f"Pushed to {topic}: {title} (HTTP {status})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
