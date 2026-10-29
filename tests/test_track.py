"""Day 3: prove claims fold into one tracked item per real deadline.

Covers alias normalisation, co-occurring aliases in one message, a bare
subject+kind claim joining an existing item, and a shared alias merging two
messages. No credits, no model — runs on the stub.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hearsay.anonymize import anonymize             # noqa: E402
from hearsay.ingest import read_messages            # noqa: E402
from hearsay.model import StubExtractor             # noqa: E402
from hearsay.prefilter import prefilter             # noqa: E402
from hearsay.schema import Message                   # noqa: E402
from hearsay.track import aliases_in, track          # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "chat.sqlite")
ROSTER = {"Dr Wilson": "FACULTY-OS", "Anmol CR": "CR"}


def _fixture_items():
    msgs = prefilter(anonymize(read_messages(FIXTURE), roster=ROSTER))
    return {it.key: it for it in track(StubExtractor().extract(msgs))}


def _msg(i, text, when, sender="FACULTY-OS"):
    return Message(id=i, group="OS", sender=sender,
                   ts=datetime(*when, tzinfo=timezone.utc), text=text,
                   is_from_me=False)


def test_alias_normalisation():
    assert aliases_in("OS FT-II (FJ2)") == {"FT-II", "FJ-II"}
    assert aliases_in("CT 1 tomorrow") == {"CT-I"}
    assert aliases_in("just lunch") == set()


def test_fixture_folds_to_two_items():
    items = _fixture_items()
    # one OS exam (FT-II, co-named FJ2) and one DSA lab — nothing else.
    assert set(items) == {"OS:FT-II", "DSA:lab"}


def test_cooccurring_aliases_land_on_one_item():
    it = _fixture_items()["OS:FT-II"]
    assert {"FT-II", "FJ-II"} <= it.aliases
    assert it.subject == "OS" and it.kind == "exam"


def test_bare_subject_kind_claim_joins_the_item():
    # msg 101 ("OS test moved to 30 Oct", no instance code) must attach to the
    # existing FT-II item, not spawn a second OS exam.
    it = _fixture_items()["OS:FT-II"]
    sources = {c.source_msg_id for c in it.history}
    assert sources == {100, 101}
    # Day 3 is naive: current_date is just the most recent dated claim (the
    # relay's 30 Oct). Day 4's trust step is what will restore faculty's 29 Oct.
    assert it.current_date == "2026-10-30"
    assert it.portion and "III" in it.portion   # portion came from the faculty line


def test_undated_lab_item_survives_without_a_date():
    it = _fixture_items()["DSA:lab"]
    assert it.kind == "lab"
    assert it.current_date is None
    assert len(it.history) == 1


def test_shared_alias_merges_across_messages():
    msgs = [
        _msg(1, "OS FT-I exam on 20 Sep 2026", (2026, 9, 10)),
        _msg(2, "OS FT-I portion is units I to II", (2026, 9, 12)),
    ]
    items = track(StubExtractor().extract(msgs))
    assert len(items) == 1
    it = items[0]
    assert "FT-I" in it.aliases
    assert len(it.history) == 2
    assert it.current_date == "2026-09-20"       # the dated claim
    assert it.portion and "II" in it.portion     # the portion-only claim


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\n{len(fns)} passed")
