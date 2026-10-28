# Hearsay — blueprint

One page, written before the code. Everything downstream should trace back to a line here.

## The problem in one sentence
My nine SRM class WhatsApp groups carry every exam date, worksheet and deadline, but buried in forwards, corrections and hearsay — a date announced by a classmate is not the same as one posted by faculty, and dates move.

## What it does
Reads the class chats, pulls out every dated item with the exact message it came from, tells a faculty announcement from an unconfirmed relay, flags when a date moves or two sources disagree, and when it can't be sure, drafts a question for me to send. Output: an ICS calendar feed, a one-screen "this week", and a morning push that quotes the source line.

## Why it fits the hackathon (and dodges the anti-projects)
Not an education chatbot and not an image analyzer. The whole value is **agentic verification**: source-linked claims, a trust order, conflict detection, and an ask-when-unsure loop. Pitched at Best Agentic; open-weight model (Muse Glimmer) for the open-weight bonus.

## The one idea that holds it together
**Replay and live are the same code on different clocks.** A fake clock lets me replay the term from 12 Sep forward, message by message, and score what the agent would have told me each day against a hand-checked log. The same pipeline, pointed at the live DB with a real clock, is the product. Nothing is "eval-only."

## Pipeline (each stage is one module)
1. **ingest** — read a *copy* of WhatsApp's `ChatStorage.sqlite` read-only, normalize to `Message(id, group, sender, ts, text, media, is_from_me)`.
2. **anonymize** — map real names/JIDs to stable roles (FA, CR, FACULTY-OS, STUDENT-xxxx) on the Mac, before anything reaches a model. Map file is gitignored.
3. **prefilter** — keep only messages that could carry a date or assessment, so the model sees a fraction of the traffic.
4. **model (Muse Glimmer)** — extract dated items: `{type, date, subject, portion, source_msg_id, confidence}`.
5. **track** — one `DeadlineItem` per real-world deadline, with history; link aliases across groups ("OS FT-II" = "OS CT 1" = "FJ2").
6. **trust** — resolve competing claims by source rank: faculty > CR > relay/forward > inference.
7. **verify** — second pass: flag moved dates, stale items, and unresolved conflicts; decide what needs a human question.
8. **outputs** — `ics.py`, `week.py`, `push.py` (ntfy, already working end-to-end).

## Eval
- **Ground truth:** `private/Deadlines_till_20_Nov_2026.md` (my AI-assisted scans — must be hand-checked before it counts as truth).
- **Metrics:** precision/recall on items, date accuracy, stale-day count, confidence calibration.
- **Baseline:** "latest message wins" (no trust, no verify). The agent has to beat it, especially on moved dates.

## Constraints that shaped choices
- **No Full Disk Access in the dev shell** → build against a synthetic fixture; a separate FDA-gated script copies the real DB.
- **16 GB M2 can't hold Glimmer** → Glimmer runs on Kaggle 2×T4 (Q4 GGUF) or hosted (Baseten); the `model` module is one interface with a stub so the rest of the pipeline runs today with no credits.
- **Public repo + waiver** → no real chat text, names or family data in the repo, ever.

## Micro-challenges (classify each before asking for help)
alias-linking across groups · relative-date + day-order resolution · calibration of confidence · making replay bit-identical to live.

## Out of scope for v1
Classroom live API (every automated route is closed; posts come in by hand). WhatsApp Cloud API send-back (business numbers only).
