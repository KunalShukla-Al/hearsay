"""A one-screen 'this week' summary in plain text.

Lists every item dated in the next `days`, oldest first, with its portion and
any flags, then a short 'need to confirm' section carrying the drafted question
for anything the agent couldn't settle on its own. Plain text so it drops into a
terminal, a note, or the body of the push unchanged.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..schema import DeadlineItem


def week_view(items: list[DeadlineItem], today: date, days: int = 7) -> str:
    end = today + timedelta(days=days)
    in_range = sorted(
        (it for it in items
         if it.current_date and today.isoformat() <= it.current_date < end.isoformat()),
        key=lambda it: it.current_date,
    )

    lines = [f"This week ({today.isoformat()} … {(end - timedelta(days=1)).isoformat()})"]
    if not in_range:
        lines.append("  nothing dated in range")
    for it in in_range:
        subject, _, name = it.key.partition(":")
        portion = f" — {it.portion}" if it.portion else ""
        flag = f"  [{', '.join(it.flags)}]" if it.flags else ""
        lines.append(f"  {it.current_date}  {subject} {name}{portion}{flag}")

    asks = [it for it in items if it.needs_question and it.question]
    if asks:
        lines.append("")
        lines.append("Need to confirm:")
        for it in asks:
            lines.append(f"  • {it.question}")

    return "\n".join(lines)
