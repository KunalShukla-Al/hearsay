"""The time-travel eval: replay the term on a fake clock and score each day.

`replay` walks the filtered messages in time order, and at each as-of date runs
the full agent pipeline (track -> trust -> verify) and the `baseline` resolver
over only the messages known by then, scoring both against a hand-checked log.
Nothing here is eval-only plumbing bolted on: it is the product pipeline with a
`FakeClock`, which is the one idea the blueprint is built around.

Import the pieces from their modules, e.g. `from hearsay.eval.replay import
replay, score` and `from hearsay.eval.baseline import latest_wins`. The CLI is
`python -m hearsay.eval.replay`; keeping this package init import-free is what
lets that run without a double-import warning.
"""
