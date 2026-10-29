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

## Day 2 — 29 Oct 2026 · extraction

**What this day adds.** `src/hearsay/model.py` — the stage that turns a filtered
message into structured `Claim`s. A message like *"OS FT-II (FJ2) on 29 Oct
2026, Units II & III"* becomes `Claim(kind="exam", subject="OS",
date="2026-10-29", portion="Units II & III", trust=FACULTY, …)`. From here on
the pipeline reasons over claims, not prose.

**The one decision everything hangs on: an `Extractor` seam.** I don't have
Glimmer running yet (no card, no Kaggle/Baseten route chosen), and I refuse to
let that block tracking, trust, verify and the eval. So the pipeline depends on
an `Extractor` protocol — `extract(messages) -> list[Claim]` — and two concrete
ones live behind it:

- `StubExtractor` — rules only, deterministic, runs today with nothing. It reads
  subject and kind from vocabulary and resolves the date forms my groups
  actually use (explicit `29 Oct 2026`, bare `30 Oct`, `dd/mm`, weekday names,
  `today`/`tomorrow`), always relative to the message's *own* send day so it
  behaves identically under replay.
- `GlimmerExtractor` — the real model behind a single `call_model(prompt) ->
  text` callable. That callable is the *only* thing that differs between the
  free Kaggle GGUF and a hosted Baseten endpoint, so the rest of the code never
  learns which route is live. It builds a strict-JSON prompt, pulls the first
  JSON block out of a chatty reply (`_first_json`), and a malformed reply drops
  that one message rather than crashing the run.

**The honest limit I built in on purpose.** Message 102 says *"try to complete
till 11th experiment"*. That `11th` is a lab count, not the 11th of a month. The
stub must **not** invent `2026-10-11` — so its date resolver only accepts an
ordinal next to a month, and returns `None` here. The claim is still created (a
real, undated DSA lab item); it just carries no date. This is deliberate: the
gap between the stub returning `None` and Glimmer reading the sentence correctly
is precisely what the Day 6 eval will measure, which is why the stub also serves
as the "rules-only floor" baseline.

**Trust comes from the sender, never the model.** `trust_of()` maps the
anonymised label (FACULTY-*, CR, STUDENT-*, me) to the `Trust` rank. I kept this
out of the model's hands on purpose — a student relay confidently asserting a
date must not outrank faculty just because the model sounded sure. Both
extractors stamp trust the same way.

**Proof.** `tests/test_model.py` (6 tests, no pytest, no credits): the faculty
announcement extracts the dated exam at FACULTY trust; the student "moved to 30
Oct" relay extracts at RELAY trust; the `11th experiment` trap resolves to
`date=None`; and `GlimmerExtractor` parses a JSON reply wrapped in chatter while
surviving a junk reply. Day 1's slice stays green (5 tests). Total 11 passing.

**Still deferred by design.** No real model call runs yet — `GlimmerExtractor`
is exercised through a fake `call_model`. Wiring the actual route is a "Then"
task once the card/Kaggle decision is made; `model.py` is the only file it
touches.

## Day 3 — 29 Oct 2026 · tracking + alias linking

**What this day adds.** `src/hearsay/track.py` turns the flat list of `Claim`s
into `DeadlineItem`s — one object per real deadline, carrying its whole history.
This is where scattered messages become a thing I can show on a calendar.

**The hard part is identity: when are two claims the same deadline?** One test
is named three ways — "OS FT-II", "CT 1", "FJ2". I link claims two ways:

1. **Shared instance alias.** `aliases_in()` pulls codes like FT-II, CT-1,
   FJ-II, LLT-I, CLA-T1 out of a line and normalises them to `PREFIX-ROMAN`
   (so "CT 1", "ct-1", "CT-I" all become `CT-I`). Message 100 says "OS FT-II
   (FJ2)", so `FT-II` and `FJ-II` co-occur in one line and bind to one item
   immediately. Across messages, any shared alias merges — and a claim whose
   aliases bridge two existing items fuses them.
2. **Bare subject+kind fallback.** Message 101, "OS test moved to 30 Oct", has
   no instance code. A no-alias claim attaches to the one open item of that
   subject and kind, so it joins FT-II instead of spawning a phantom second OS
   exam. If there's zero or more than one candidate, it starts its own item
   rather than guess.

**Why claims are folded in time order.** I sort by `source_ts` before folding,
so the faculty announcement (13 Oct) creates the FT-II item before the vaguer
relay (25 Oct) arrives to join it. That meant `Claim` needed to carry *when* it
was asserted — I added `source_ts` to the schema and both extractors stamp it
from the message. Stale-detection on Day 4 will lean on the same field.

**The canonical key.** `OS:FT-II`, `DSA:lab`. When an item has instance aliases,
the key prefers the written-test name (FT > CT > LLT > CLA-T > LLJ > FJ) so the
same test keys the same way however it was first mentioned; with no alias it
falls back to `subject:kind`.

**What I deliberately did NOT do today.** The fixture holds a real contradiction
— faculty say the OS exam is 29 Oct, a student says it "moved to 30 Oct". Day 3
does not adjudicate it. `current_date` is naively the most recently asserted
dated claim, so right now the item reads 30 Oct — the *wrong* answer — and both
claims sit in its history. Fixing that (trust-weighting faculty over a relay,
and raising `moved` / `conflict` flags with an ask-when-unsure draft) is exactly
Day 4's job. I wrote the test to assert the naive 30 Oct on purpose, so Day 4's
change is visible as the item flipping back to 29 Oct.

**Proof.** `tests/test_track.py` (6 tests): alias normalisation; the fixture
folding to exactly `{OS:FT-II, DSA:lab}`; co-occurring aliases landing on one
item; the bare relay joining FT-II (history `{100, 101}`); the undated DSA lab
surviving with `current_date=None`; and a shared `FT-I` alias merging two
synthetic messages. Days 1–2 stay green after the schema change. **17 passing.**

### Plan for the rest of the week
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
