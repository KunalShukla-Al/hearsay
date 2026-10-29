"""Day 2: prove extraction turns candidate messages into Claims.

Runs the stub against the fixture (no credits, no model), and proves the real
GlimmerExtractor parses a model reply through an injected fake call.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hearsay.anonymize import anonymize             # noqa: E402
from hearsay.ingest import read_messages            # noqa: E402
from hearsay.model import (                          # noqa: E402
    GlimmerExtractor, StubExtractor, trust_of,
)
from hearsay.prefilter import prefilter             # noqa: E402
from hearsay.schema import Trust                     # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "chat.sqlite")
ROSTER = {"Dr Wilson": "FACULTY-OS", "Anmol CR": "CR"}


def _candidates():
    msgs = anonymize(read_messages(FIXTURE), roster=ROSTER)
    return prefilter(msgs)


def _stub_by_source():
    return {c.source_msg_id: c for c in StubExtractor().extract(_candidates())}


def test_faculty_announcement_extracts_dated_exam():
    c = _stub_by_source()[100]
    assert c.subject == "OS"
    assert c.kind == "exam"
    assert c.date == "2026-10-29"        # "29 Oct 2026"
    assert c.trust is Trust.FACULTY
    assert c.confidence >= 0.85
    assert c.portion and "III" in c.portion


def test_student_relay_is_lower_trust():
    c = _stub_by_source()[101]
    assert c.subject == "OS"
    assert c.date == "2026-10-30"        # "moved to 30 Oct", no year -> message's year
    assert c.trust is Trust.RELAY        # unpinned student


def test_bare_ordinal_is_not_a_calendar_date():
    # "till 11th experiment" is a lab count, not a date. The stub must leave the
    # date unresolved rather than invent 2026-10-11 — that reading is the model's.
    c = _stub_by_source()[102]
    assert c.subject == "DSA"
    assert c.kind == "lab"
    assert c.date is None
    assert c.trust is Trust.CR


def test_trust_mapping():
    assert trust_of("FACULTY-OS") is Trust.FACULTY
    assert trust_of("CR") is Trust.CR
    assert trust_of("STUDENT-ab12") is Trust.RELAY
    assert trust_of("me") is Trust.INFERENCE


def test_glimmer_parses_model_reply():
    # A fake Glimmer that returns chatty text wrapping a JSON array.
    def fake_call(prompt: str) -> str:
        return ('Sure! Here is the extraction:\n'
                '[{"kind":"exam","subject":"OS","date":"2026-10-29",'
                '"portion":"Units II & III","confidence":0.95}]\n'
                'Let me know if you need more.')

    claims = GlimmerExtractor(fake_call).extract(_candidates())
    assert claims, "expected at least one parsed claim"
    c = claims[0]
    assert c.subject == "OS" and c.date == "2026-10-29"
    assert c.confidence == 0.95
    assert c.trust is Trust.FACULTY      # trust still comes from the sender, not the model


def test_glimmer_survives_a_bad_reply():
    # A reply with no JSON must drop the message, never raise.
    claims = GlimmerExtractor(lambda _p: "no idea, sorry").extract(_candidates())
    assert claims == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\n{len(fns)} passed")
