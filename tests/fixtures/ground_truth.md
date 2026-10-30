# Fixture ground truth

The hand-checked deadlines in the synthetic test chat (`chat.sqlite`), so the
replay eval scores against something real without touching private data. The
actual term log lives at `private/Deadlines_till_20_Nov_2026.md` (git-ignored)
in this same `key | date | portion` shape and is passed with `--truth`.

`date` is an ISO date, or `none` for an item that exists but carries no date yet
(the agent should surface it and ask, not invent one).

| key | date | portion |
| --- | --- | --- |
| OS:FT-II | 2026-10-29 | Units II & III |
| DSA:lab | none | |
