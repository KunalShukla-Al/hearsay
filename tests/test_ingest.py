"""Prove the ingest -> anonymize -> prefilter slice on the synthetic fixture.

Runs with no Full Disk Access and no model credits, so the vertical is green
from day one.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hearsay.anonymize import anonymize          # noqa: E402
from hearsay.ingest import read_messages          # noqa: E402
from hearsay.prefilter import prefilter           # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "chat.sqlite")


def _load():
    msgs = read_messages(FIXTURE)
    return msgs


def test_ingest_reads_all_messages():
    msgs = _load()
    assert len(msgs) == 5
    # chronological order
    assert [m.id for m in msgs] == sorted(m.id for m in msgs) or \
        all(msgs[i].ts <= msgs[i + 1].ts for i in range(len(msgs) - 1))


def test_timestamp_converts_from_cfabsolute():
    msgs = {m.id: m for m in _load()}
    # message 100 was written for 2026-10-13
    assert msgs[100].ts.year == 2026 and msgs[100].ts.month == 10


def test_group_and_sender_resolve():
    msgs = {m.id: m for m in _load()}
    assert msgs[100].group == "DSA 2026"
    assert msgs[100].sender == "Dr Wilson"
    assert msgs[104].is_from_me and msgs[104].sender == "me"


def test_anonymize_pins_roles_and_pseudonymizes_rest():
    msgs = anonymize(_load(), roster={"Dr Wilson": "FACULTY-OS", "Anmol CR": "CR"})
    by_id = {m.id: m for m in msgs}
    assert by_id[100].sender == "FACULTY-OS"
    assert by_id[102].sender == "CR"
    assert by_id[101].sender.startswith("STUDENT-")   # unknown -> pseudonym
    assert by_id[104].sender == "me"                   # mine untouched


def test_prefilter_keeps_dated_assessments_drops_chatter():
    kept = {m.id for m in prefilter(_load())}
    assert 100 in kept   # faculty date announcement
    assert 102 in kept   # CR lab deadline
    assert 103 not in kept  # "lunch 🍕"
    assert 104 not in kept  # "thanks sir"


if __name__ == "__main__":
    # tiny runner so the slice works without pytest installed
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\n{len(fns)} passed")
