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

## Day 4 — 29 Oct 2026 · trust + verify

**What this day adds.** Two small modules that turn a pile of tracked history
into one trustworthy answer plus an honest list of caveats. `trust.py` chooses
the date; `verify.py` flags what a human should still check and drafts the
question to send. This is the "verified, source-linked" half of the pitch — the
part that separates the project from a basic chatbot for the judges.

**trust.resolve — rank, then recency.** Among the dated claims on an item it
takes the highest rank (FACULTY > CR > RELAY > INFERENCE), and within a rank the
most recent. On the fixture that flips the OS exam from the Day-3 naive *30 Oct*
(the student's later rumor) back to the faculty's **29 Oct**. The losers are not
deleted — they stay in history so the next step can point at them.

**verify — three flags, and the discipline of when to ask.**
- **moved**: the winning rank asserted more than one date over time — a real
  reschedule. A later faculty "moved to 30 Oct" correctly wins, and the item is
  flagged so the change is visible.
- **conflict**: a different rank disagrees with the chosen date. The student's
  "30 Oct" rumor raises this even though faculty overrules it — surfaced, never
  hidden.
- **stale**: the date is still upcoming but nothing has confirmed it in
  `stale_days` (14) — worth a re-check. Needs the clock, so `verify` takes
  `today`; replay will pass a `FakeClock`'s day and get the same verdicts.

The judgement I care about most: **when does the agent actually ask?** Only when
it is genuinely unsure — an undated item, or a disagreement with *no* faculty
backing. The fixture's rumor is flagged but asks nothing, because faculty
already settles it; nagging about a rumor the rank system overrules would make
the tool annoying. An unbacked CR-vs-classmate split *does* ask, and the drafted
line quotes both dates with who said each and when, ready to paste to the CR.
The undated DSA lab asks for a date and quotes the exact source line. I added a
`question` field to the schema to carry that draft.

**Proof.** `tests/test_verify.py` (6 tests): faculty beats the relay and the
fixture date becomes 29 Oct with a `conflict` flag; the overruled rumor asks
nothing; the undated lab asks "when is it due?"; a two-post faculty reschedule
flags `moved` and asks nothing; an unbacked CR-vs-classmate split asks with both
options; and a long-unconfirmed upcoming date flags `stale`. Days 1–3 stay
green. **23 passing.**

## Day 5 — 29 Oct 2026 · outputs

**What this day adds.** `src/hearsay/outputs/` — the three surfaces a person
actually sees, each reading the resolved `DeadlineItem`s and nothing else, so one
set of items drives all of them.

- **`ics.py` — a calendar feed.** Every dated item becomes an all-day VEVENT the
  phone can subscribe to. The detail I care about: the DESCRIPTION cites the
  claim that *backs the chosen date* (highest trust, then most recent), so the
  fixture's OS entry reads "source (faculty): OS FT-II (FJ2) on 29 Oct …" — the
  faculty post, not the later "moved to 30 Oct" rumor. Undated items (the DSA
  lab) carry no date, so they stay out of the calendar and surface in the week
  view instead. Text is escaped and long lines folded per RFC 5545 so it
  validates in Apple/Google Calendar — checked the rendered file by eye.
- **`week.py` — a one-screen week.** Plain text: everything dated in the next 7
  days, oldest first, with portion and flags, then a "Need to confirm" section
  carrying the drafted questions. The fixture shows `2026-10-29 OS FT-II … [conflict]`
  and the DSA lab's "when is it due?".
- **`push.py` — the ntfy morning push.** `compose` builds a short title/body (a
  push can't deep-link to one message, so it names items and counts what needs
  confirming); `send` POSTs to `ntfy.sh/<topic>` with the HTTP call injectable,
  so tests and replay never fire a real push. The topic is passed in (read from
  `~/.config/noticeagent/ntfy-topic`), never committed.

**Proof.** `tests/test_outputs.py` (6 tests): one VEVENT for the dated exam and
none for the undated lab; the DESCRIPTION cites the faculty claim and not the
rumor; commas are escaped; the week view lists the exam with its conflict flag
and the lab's question; the push counts "1 this week" + "1 to confirm"; and
`send` uses an injected post rather than the network. All prior days green.
**29 passing.**

**Open for me to decide when I'm back.** The push needs a trigger — a 06:55
`pmset` wake plus a launch agent that runs ingest→…→send once. That's a Mac
wiring task (and needs Full Disk Access for the real DB), so it waits until I'm
at the keyboard; the composing and sending are done and tested.

## Day 6 — 30 Oct 2026 · the time-travel eval

**What this day adds.** `src/hearsay/eval/` — `replay.py` and `baseline.py`, the
scoring harness that makes "the agent is better than just reading the latest
message" a number instead of a claim. This is the day the blueprint's one idea
(*replay and live are the same pipeline on different clocks*) finally earns its
keep: the replay reasons over the past by sliding a `FakeClock`, nothing more.

**The baseline I have to beat.** `baseline.py` is "latest message wins": take the
most recently asserted date per tracked item, no source rank, no verify, no
questions. It deliberately reuses `track`'s alias-linking, so the *only* thing
separating it from the agent is trust + verify — which is exactly the thing the
eval is meant to price. If the agent can't beat this, the whole verification
pitch is hot air.

**How a day of replay works.** `agent_view(messages, instant)` sets a `FakeClock`
to `instant`, keeps only the messages at or before it, and runs the real
pipeline — `track -> adjudicate` (trust then verify) with `today = instant`.
`baseline_view` does the same but ends in `latest_wins`. So "what would the agent
have told me on 21 Oct?" is just the clock sitting at 21 Oct over the messages
that existed then. Extraction runs on the slice, not on everything-then-filtered,
so a real Glimmer later only ever sees past messages — replay stays honest about
what was knowable.

**Scoring, and the one trap I avoided.** `score()` gives recall and precision on
*which* deadlines surfaced, and date accuracy on the ones that should carry a
date. The trap: an undated item (the DSA lab) must count as *right* only when the
view also leaves it undated — rewarding a guess there would reward exactly the
hallucination the `11th experiment` test was built to forbid. So undated items
are scored separately (`undated_held`) and never fold into date accuracy.

**Ground truth without leaking anything.** The eval scores against a
`key | date | portion` Markdown table. The real term log is private and
git-ignored (`private/Deadlines_till_20_Nov_2026.md`), so I committed a tiny
`tests/fixtures/ground_truth.md` for the synthetic chat and made `--truth` point
the same parser at the real file when I run it on my Mac. The eval therefore runs
today, in CI-less `python tests/test_eval.py`, with no private data and no model.

**The headline the replay prints.** On the fixture, three dates matter: faculty
announce FT-II for 29 Oct (13 Oct), the DSA lab arrives undated (21 Oct), then a
classmate relays "moved to 30 Oct" (25 Oct). The timeline shows agent and
baseline *agreeing* at 1/1 until the 25th — then the baseline drops to 0/1 (it
takes the rumour) while the agent holds 29 Oct on faculty's rank. Date accuracy
1/1 vs 0/1 on the one contested deadline, which is the whole product in one line.

**Where I placed it, and why not top-level.** The plan wrote `eval/replay.py`;
I put it under `src/hearsay/eval/` instead, a sub-package beside `outputs/`. It
shares the pipeline imports cleanly and is import-testable like everything else,
and `python -m hearsay.eval.replay` is the demo command. `__init__.py` is kept
import-free on purpose — re-exporting the module that also runs under `-m` gives
a double-import warning that would show up on camera.

**Proof.** `tests/test_eval.py` (6 tests): the truth table parses dated and
undated items; after the rumour the agent holds 29 Oct and the baseline takes
30; the final score has both at full recall but agent date accuracy above
baseline; before the rumour they agree (so the gap is provably the rumour's
doing); and the replay timeline diverges only on the 25th. Days 1–5 stay green.
**35 passing.**

**Still deferred by design.** Confidence calibration is in the blueprint's metric
list but waits for real Glimmer — the stub's confidence is a constant, so
calibrating it would measure nothing. Same for a precision/recall curve over a
large real log; the fixture has two items. Both land once the model route is live
and the private log is hand-checked.

### Plan for the rest of the week
- **Then:** real Glimmer (Kaggle or Baseten), the 3-minute demo video, README.

### Open for me to decide when I'm back
- Repo name (shipped as `hearsay` — the agent's job is to turn hearsay into
  verified, source-linked facts; rename if I dislike it).
- Model route: Kaggle GGUF (free, qualifies for the open-weight bonus) vs
  hosted Baseten (needs a card). The code doesn't care; only `model.py`'s config
  changes.
