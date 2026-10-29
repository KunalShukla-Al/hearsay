"""Day 4: trust resolves the winning date; verify flags and drafts questions.

The headline case is the fixture contradiction — faculty 29 Oct vs a student's
"moved to 30 Oct" — which Day 3 left reading 30. After adjudication it must read
29, flag the rumor, and ask nothing.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hearsay.anonymize import anonymize             # noqa: E402
from hearsay.ingest import read_messages            # noqa: E402
from hearsay.model import StubExtractor             # noqa: E402
from hearsay.prefilter import prefilter             # noqa: E402
from hearsay.schema import Message                   # noqa: E402
from hearsay.track import track                      # noqa: E402
from hearsay.verify import adjudicate                # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "chat.sqlite")
ROSTER = {"Dr Wilson": "FACULTY-OS", "Anmol CR": "CR"}


def _fixture(today=date(2026, 10, 28)):
    msgs = prefilter(anonymize(read_messages(FIXTURE), roster=ROSTER))
    items = track(StubExtractor().extract(msgs))
    return {it.key: it for it in adjudicate(items, today)}


def _msg(i, text, when, sender):
    return Message(id=i, group="OS", sender=sender,
                   ts=datetime(*when, tzinfo=timezone.utc), text=text,
                   is_from_me=False)


def _items(messages, today):
    return adjudicate(track(StubExtractor().extract(messages)), today)


def test_faculty_beats_relay_and_fixes_the_date():
    it = _fixture()["OS:FT-II"]
    assert it.current_date == "2026-10-29"       # was 30 after Day 3; trust restores 29
    assert "conflict" in it.flags                # the rumor is surfaced, not hidden


def test_overruled_rumor_asks_nothing():
    it = _fixture()["OS:FT-II"]
    assert it.needs_question is False            # faculty backs the date, so no nag
    assert it.question is None


def test_undated_item_asks_for_a_date():
    it = _fixture()["DSA:lab"]
    assert it.needs_question is True
    assert it.question and "when is it due" in it.question.lower()
    assert "DSA" in it.question


def test_faculty_reschedule_flags_moved():
    msgs = [
        _msg(1, "OS FT-II on 29 Oct 2026", (2026, 10, 13), "FACULTY-OS"),
        _msg(2, "OS FT-II moved to 30 Oct 2026", (2026, 10, 27), "FACULTY-OS"),
    ]
    it = _items(msgs, date(2026, 10, 28))[0]
    assert it.current_date == "2026-10-30"       # latest faculty wins
    assert "moved" in it.flags
    assert it.needs_question is False            # a clean reschedule needs no question


def test_unbacked_conflict_asks_with_both_options():
    msgs = [
        _msg(1, "OS viva on 5 Nov 2026", (2026, 11, 1), "CR"),
        _msg(2, "OS viva maybe 6 Nov 2026", (2026, 11, 1), "STUDENT-ab12"),
    ]
    it = _items(msgs, date(2026, 11, 1))[0]
    assert it.current_date == "2026-11-05"       # CR outranks the classmate
    assert it.needs_question is True             # but no faculty confirms it
    assert "2026-11-05" in it.question and "2026-11-06" in it.question


def test_stale_when_nothing_confirms_recently():
    msgs = [_msg(1, "FDS FT-IV on 1 Dec 2026", (2026, 10, 1), "FACULTY-FDS")]
    it = _items(msgs, date(2026, 10, 28))[0]
    assert it.current_date == "2026-12-01"
    assert "stale" in it.flags                   # upcoming, but last heard 27 days ago
    assert it.needs_question is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\n{len(fns)} passed")
