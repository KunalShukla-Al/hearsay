# Build log

A running journal of what I built, why, and how — in reading order, so I can
catch up after a week away from the keyboard. Newest entry at the bottom.

How to use this during catch-up: read top to bottom with the repo open. Each
entry names the files it touched and the reasoning behind each choice. The git
history mirrors these entries one-to-one, so a `git log --oneline` is the same
story in headlines.

---

## Day 1 — 28 Oct 2026 · foundation

**Why I'm writing this way.** It's test week (OS FT-II on the 29th, and more),
so I can't be at the keyboard. The deal: the code gets written now, and this log
plus granular commits record every decision so I own it properly once tests end.
This is a one-week exception to my usual rule that I write my own project code —
not a handover. When I'm back I read this log, re-derive the choices, and take
the wheel.

**First decision: build before code.** I wrote `BLUEPRINT.md` first — one page
fixing what the thing does and, as much, what it leaves out. The load-bearing
idea there is that *replay and live are the same pipeline on different clocks*.
Every later module is built to not know or care which clock it's on.

**Second decision: how to handle the WhatsApp data.** The data lives in
`~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite`.
Two facts forced the shape of ingest:

1. macOS won't let the dev shell read that file — no Full Disk Access — so I
   can't develop against live data from here. Rather than block the whole week
   on a system-settings toggle, I build against a **synthetic fixture** that
   mimics WhatsApp's Core Data schema, and put the one privileged step (copying
   the real DB) in `scripts/pull_whatsapp.py`, to be run by something that has
   FDA. When that runs, I check my schema mapping against the real tables and
   fix the thin layer in `ingest.py` if WhatsApp's columns differ from my notes.
2. The repo is public and the hackathon waiver hands organizers a licence to
   anything in it. So real names, real chat text, and the ground-truth log never
   enter git — see `.gitignore`. Anonymization happens on the Mac, before a
   model ever sees a message.

**What a message looks like after ingest.** WhatsApp stores time as CFAbsolute
(seconds since 2001-01-01), chats in `ZWACHATSESSION`, messages in `ZWAMESSAGE`,
and the sender of a group message in `ZWAGROUPMEMBER`. `ingest.py` joins those
and flattens each row into a plain `Message` (see `schema.py`): an id, the group
name, who sent it, a real UTC timestamp, the text, any media path, and whether I
sent it. Everything upstream speaks `Message`; nothing else touches SQLite.

**The clock.** `clock.py` is tiny but central. A `RealClock` reads the wall
clock; a `FakeClock` is pinned to a chosen instant and can be stepped forward.
Replay walks messages in time order and advances a `FakeClock` to each message's
timestamp, so "what did the agent know on 14 Oct?" is just the fake clock sitting
at 14 Oct. The product is the identical pipeline with a `RealClock`.

**First vertical slice, end to end on the fixture:** ingest → anonymize →
prefilter.
- `anonymize.py` maps each real sender to a stable pseudonym by role (FA, CR,
  FACULTY, STUDENT-xxxx) using a salted hash, so the same person always gets the
  same label and the mapping never needs to store the real name in the repo.
- `prefilter.py` drops the chatter. Only messages carrying a date cue or an
  assessment word (FT, CT, LLT, LLJ, exam, viva, worksheet, due, submit, …)
  survive to reach the model. This is what keeps a 90 MB chat history down to a
  model bill I can afford.

`scripts/make_fixture.py` writes a small SQLite DB in WhatsApp's shape with a
handful of realistic messages (a faculty date announcement, a student relay that
contradicts it, pure chatter). `tests/test_ingest.py` runs the slice against it
and asserts the counts, so the vertical is proven today with no credits and no
FDA.

**What's stubbed and why.** The model call, tracking, trust, verify and the ICS
/ week / push outputs are named in the blueprint but not built yet — they come on
their own days (see the plan below). I'd rather have one slice that genuinely
runs than eight half-files.

**One real fix while testing the slice.** The CR message "try to complete till
11th experiment" was dropped by `prefilter` — my date regex wanted a month, and
a bare ordinal plus "experiment" didn't match. But that's a genuine lab deadline
(it's in my real log), so dropping it is a recall miss, and recall is the thing
prefilter must not lose. I loosened the net: bare ordinals ("11th") count as a
date cue, and "experiment"/"exercise"/"ex" count as assessment words. The test
now asserts this message survives.

### Plan for the rest of the week
- **Day 2:** `model.py` — the Muse Glimmer interface with a deterministic stub
  extractor, so `track` can be built and tested before any credits land.
- **Day 3:** `track.py` + alias-linking ("OS FT-II" = "CT 1" = "FJ2").
- **Day 4:** `trust.py` + `verify.py` — source ranking, moved-date and conflict
  flags, the ask-when-unsure draft.
- **Day 5:** `outputs/` — ICS feed, one-screen week, wire up the ntfy push.
- **Day 6:** `eval/replay.py` + `eval/baseline.py` — time-travel scoring vs the
  hand-checked log, against "latest message wins".
- **Then:** real Glimmer (Kaggle or Baseten), the 3-minute demo video, README.

### Open for me to decide when I'm back
- Repo name (shipped as `hearsay` — the agent's job is to turn hearsay into
  verified, source-linked facts; rename if I dislike it).
- Model route: Kaggle GGUF (free, qualifies for the open-weight bonus) vs
  hosted Baseten (needs a card). The code doesn't care; only `model.py`'s config
  changes.
