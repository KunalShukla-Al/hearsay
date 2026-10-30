"""Day 7: the live entry point — the same pipeline as replay, on a real clock.

The point to prove is that "live" is not a second implementation: the product's
`pipeline` is exactly what the replay eval scores, so what I'd be told live is
what the eval measured. Here that is pinned with a FakeClock via --as-of and
checked against the eval's own agent_view.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hearsay.eval.replay import agent_view                      # noqa: E402
from hearsay.run import load_messages, main, pipeline           # noqa: E402

HERE = os.path.dirname(__file__)
FIXTURE = os.path.join(HERE, "fixtures", "chat.sqlite")
ROSTER = {"Dr Wilson": "FACULTY-OS", "Anmol CR": "CR"}


def _messages():
    return load_messages(FIXTURE, None)


def _at(day):
    return datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)


def test_load_messages_keeps_only_the_dated_traffic():
    msgs = _messages()
    # the two chatter lines are dropped by prefilter; three dated ones remain
    assert len(msgs) == 3
    assert all(m.sender.startswith(("FACULTY", "CR", "STUDENT")) for m in msgs)


def test_pipeline_resolves_the_fixture_like_the_rest_of_the_app():
    items = {it.key: it for it in pipeline(_messages(), date(2026, 10, 28))}
    assert items["OS:FT-II"].current_date == "2026-10-29"   # trust, not the rumour
    assert items["DSA:lab"].current_date is None


def test_live_pipeline_is_the_same_as_the_replay_agent_view():
    msgs = _messages()
    instant = _at(date(2026, 10, 28))
    known = [m for m in msgs if m.ts <= instant]
    live = {it.key: it for it in pipeline(known, instant.date())}
    replayed = agent_view(msgs, instant)
    assert live.keys() == replayed.keys()
    for key in live:
        assert live[key].current_date == replayed[key].current_date
        assert live[key].flags == replayed[key].flags


def test_cli_runs_the_week_and_ics_surfaces():
    assert main(["--db", FIXTURE, "--as-of", "2026-10-28", "--out", "week"]) == 0
    assert main(["--db", FIXTURE, "--as-of", "2026-10-28", "--out", "ics"]) == 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\n{len(fns)} passed")
