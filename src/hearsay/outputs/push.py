"""Compose and send the morning push through ntfy.

`compose` turns the resolved items into a short title and body — a push can't
deep-link to one WhatsApp message, so it names the items and counts what still
needs confirming. `send` POSTs to ntfy.sh/<topic>; the HTTP call is injectable
(`post`), so tests and replay never fire a real push. The topic is passed in by
the caller, read from ~/.config/noticeagent/ntfy-topic, and never committed.
"""

from __future__ import annotations

import urllib.request
from datetime import date, timedelta
from typing import Callable

from ..schema import DeadlineItem


def compose(items: list[DeadlineItem], today: date, days: int = 7) -> tuple[str, str]:
    end = today + timedelta(days=days)
    in_range = sorted(
        (it for it in items
         if it.current_date and today.isoformat() <= it.current_date < end.isoformat()),
        key=lambda it: it.current_date,
    )

    title = f"Hearsay: {len(in_range)} this week" if in_range else "Hearsay: nothing due this week"

    body_lines = []
    for it in in_range:
        subject, _, name = it.key.partition(":")
        body_lines.append(f"{it.current_date} {subject} {name}")
    asks = sum(1 for it in items if it.needs_question)
    if asks:
        body_lines.append(f"{asks} to confirm")

    return title, "\n".join(body_lines) if body_lines else "All clear."


def _http_post(topic: str, title: str, body: str) -> int:
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=body.encode(),
        headers={"Title": title}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


def send(items: list[DeadlineItem], today: date, topic: str,
         post: Callable[[str, str, str], int] = _http_post) -> int:
    title, body = compose(items, today)
    return post(topic, title, body)
