# Hearsay

Turn class-chat hearsay into a verified, source-linked calendar.

My nine SRM class WhatsApp groups carry every exam date, worksheet and deadline
— buried in forwards, corrections and rumours. A date a classmate relays is not
a date faculty announced, and dates move. Hearsay reads the chats, pulls out
every dated item with the exact message it came from, ranks sources (faculty >
CR > relay), flags moved dates and conflicts, and when it can't be sure, drafts
the question for me to ask. It emits an ICS feed, a one-screen "this week", and a
morning push that quotes the source line.

Built for the Meta Global AI Developer Hackathon (Indie track). It leans on the
agentic, verifiable core rather than being a chatbot: source-linked claims, a
trust order, conflict detection, and an ask-when-unsure loop. The extraction
model is the open-weight **Muse Glimmer**.

## The one idea
Replay and live are the same pipeline on different clocks. A fake clock replays
the term from 12 Sep forward, message by message, scoring what the agent would
have told me each day against a hand-checked log. The same code on a real clock
is the product.

## Run the slice (no model, no WhatsApp access needed)
```bash
python scripts/make_fixture.py tests/fixtures/chat.sqlite
python tests/test_ingest.py
```

## Score it (the replay eval)
Replay the term on a fake clock and score the agent against "latest message
wins", day by day:
```bash
python tests/test_eval.py                    # the 6 scoring tests
PYTHONPATH=src python -m hearsay.eval.replay  # the timeline + headline
```
On the synthetic fixture the baseline flips to a classmate's wrong "moved to 30
Oct" the day it lands, while the agent holds faculty's 29 Oct — date accuracy
1/1 vs 0/1 on the contested deadline. It scores against a committed
`tests/fixtures/ground_truth.md`; point it at the real, git-ignored term log
with `--truth private/Deadlines_till_20_Nov_2026.md` (same `key | date | portion`
shape) and `--db`/`--roster` for real chats.

## Run it live
Same pipeline as the eval, on a real clock, feeding the output surfaces:
```bash
PYTHONPATH=src python -m hearsay.run                    # this week's view (fixture)
PYTHONPATH=src python -m hearsay.run --out ics          # the calendar feed
PYTHONPATH=src python -m hearsay.run --as-of 2026-10-28 # what I'd have seen that day
```
`--as-of <iso>` pins a fake clock and shows only what was known by then, so live
and replay are literally the same `pipeline()` — the eval asserts they match
key‑for‑key. With no flag it reads the whole chat at the real clock. `--out push`
sends to an ntfy topic (`--ntfy-topic` or `~/.config/noticeagent/ntfy-topic`) and
is the only path that touches the network.

## Pointing it at real chats
```bash
# one-time: grant Full Disk Access to your terminal, then:
python scripts/pull_whatsapp.py      # copies the DB into private/ (gitignored)
```
Real names and chat text never enter this repo — anonymization runs on the Mac
before any message reaches a model, and `private/` is git-ignored.

See `BLUEPRINT.md` for the design and `BUILD_LOG.md` for the day-by-day record.
