"""Day 5: the calendar feed, the week view, and the push.

Drives everything from the adjudicated fixture items, so the outputs reflect the
same trust-resolved deadlines the earlier days produce.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hearsay.anonymize import anonymize             # noqa: E402
from hearsay.ingest import read_messages            # noqa: E402
from hearsay.model import StubExtractor             # noqa: E402
from hearsay.outputs import compose, send, to_ics, week_view  # noqa: E402
from hearsay.prefilter import prefilter             # noqa: E402
from hearsay.track import track                      # noqa: E402
from hearsay.verify import adjudicate                # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "chat.sqlite")
ROSTER = {"Dr Wilson": "FACULTY-OS", "Anmol CR": "CR"}
TODAY = date(2026, 10, 28)


def _items():
    msgs = prefilter(anonymize(read_messages(FIXTURE), roster=ROSTER))
    return adjudicate(track(StubExtractor().extract(msgs)), TODAY)


def test_ics_has_one_all_day_event_for_the_dated_exam():
    ics = to_ics(_items(), stamp=datetime(2026, 10, 28, 6, 55, tzinfo=timezone.utc))
    assert ics.startswith("BEGIN:VCALENDAR")
    assert ics.rstrip().endswith("END:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == 1          # only OS FT-II is dated; DSA lab is not
    assert "DTSTART;VALUE=DATE:20261029" in ics    # faculty's 29 Oct, not the rumor's 30
    assert "SUMMARY:OS FT-II" in ics


def test_ics_description_cites_the_backing_faculty_claim():
    ics = to_ics(_items())
    # the source line must be the faculty announcement, not the 30 Oct relay
    assert "source (faculty)" in ics
    assert "29 Oct" in ics
    assert "moved to 30 Oct" not in ics


def test_ics_escapes_special_characters():
    items = _items()
    ics = to_ics(items)
    # the faculty text "Units II & III, 50 marks" carries a comma -> must be escaped
    assert "\\," in ics


def test_week_view_lists_the_exam_and_the_question():
    view = week_view(_items(), TODAY)
    assert "2026-10-29  OS FT-II" in view
    assert "[conflict]" in view                    # the surfaced rumor
    assert "Need to confirm:" in view
    assert "DSA lab" in view                        # the undated lab asks for a date


def test_compose_push_counts_week_and_confirmations():
    title, body = compose(_items(), TODAY)
    assert title == "Hearsay: 1 this week"
    assert "2026-10-29 OS FT-II" in body
    assert "1 to confirm" in body                   # the DSA lab


def test_send_uses_injected_post_not_the_network():
    sent = {}

    def fake_post(topic, title, body):
        sent.update(topic=topic, title=title, body=body)
        return 200

    status = send(_items(), TODAY, topic="hearsay-abc123", post=fake_post)
    assert status == 200
    assert sent["topic"] == "hearsay-abc123"
    assert sent["title"].startswith("Hearsay:")
    assert "OS FT-II" in sent["body"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\n{len(fns)} passed")
