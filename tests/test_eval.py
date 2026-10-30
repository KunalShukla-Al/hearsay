"""Day 6: the time-travel eval — replay the term and score agent vs baseline.

The headline the whole project is pitched on: on the day the "moved to 30 Oct"
rumour lands, the baseline ("latest message wins") flips to the wrong date while
the agent, ranking faculty over a relay, stays on 29 Oct. The replay must make
that divergence appear exactly when the rumour arrives and not before.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hearsay.anonymize import anonymize                              # noqa: E402
from hearsay.eval.replay import agent_view, baseline_view, parse_truth, replay, score  # noqa: E402
from hearsay.ingest import read_messages                            # noqa: E402
from hearsay.prefilter import prefilter                             # noqa: E402

HERE = os.path.dirname(__file__)
FIXTURE = os.path.join(HERE, "fixtures", "chat.sqlite")
TRUTH = os.path.join(HERE, "fixtures", "ground_truth.md")
ROSTER = {"Dr Wilson": "FACULTY-OS", "Anmol CR": "CR"}


def _messages():
    return prefilter(anonymize(read_messages(FIXTURE), roster=ROSTER))


def _truth():
    with open(TRUTH, encoding="utf-8") as fh:
        return parse_truth(fh.read())


def _at(day):
    return datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)


def test_truth_parses_dated_and_undated_items():
    truth = _truth()
    assert set(truth) == {"OS:FT-II", "DSA:lab"}
    assert truth["OS:FT-II"].date == "2026-10-29"
    assert truth["DSA:lab"].date is None                 # exists, but no date


def test_agent_holds_the_faculty_date_after_the_rumour():
    view = agent_view(_messages(), _at(date(2026, 10, 26)))
    assert view["OS:FT-II"].current_date == "2026-10-29"  # trust beats the later relay
    assert view["DSA:lab"].current_date is None


def test_baseline_takes_the_rumour_after_it_lands():
    view = baseline_view(_messages(), _at(date(2026, 10, 26)))
    assert view["OS:FT-II"].current_date == "2026-10-30"  # latest message wins — wrong


def test_final_score_agent_beats_baseline_on_dates():
    truth, msgs, day = _truth(), _messages(), date(2026, 10, 25)
    agent = score(agent_view(msgs, _at(day)), truth, day)
    base = score(baseline_view(msgs, _at(day)), truth, day)
    assert agent.recall == 1.0 and base.recall == 1.0     # both find both deadlines
    assert agent.date_correct == 1 and agent.date_total == 1   # 29 Oct, right
    assert agent.undated_correct == 1                     # DSA lab held undated
    assert base.date_correct == 0                         # 30 Oct, wrong
    assert agent.date_accuracy > base.date_accuracy


def test_they_agree_before_the_rumour_arrives():
    truth, msgs, day = _truth(), _messages(), date(2026, 10, 21)
    agent = score(agent_view(msgs, _at(day)), truth, day)
    base = score(baseline_view(msgs, _at(day)), truth, day)
    # Only faculty's 29 Oct is in yet, so both are right — the gap is the rumour's doing.
    assert agent.date_correct == base.date_correct == 1
    assert not agent.wrong and not base.wrong


def test_replay_timeline_diverges_only_on_the_rumour_day():
    rows = replay(_messages(), _truth())
    by_day = {day: (agent, base) for day, agent, base in rows}
    assert set(by_day) == {date(2026, 10, 13), date(2026, 10, 21), date(2026, 10, 25)}
    for day in (date(2026, 10, 13), date(2026, 10, 21)):
        agent, base = by_day[day]
        assert agent.date_accuracy == base.date_accuracy == 1.0
    agent, base = by_day[date(2026, 10, 25)]
    assert agent.date_accuracy == 1.0 and base.date_accuracy == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\n{len(fns)} passed")
