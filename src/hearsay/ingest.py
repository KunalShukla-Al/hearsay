"""Read a copy of WhatsApp's ChatStorage.sqlite and emit normalized Messages.

This is the only module that touches SQLite. It opens the DB read-only and
expects a *copy* — never the live file (see scripts/pull_whatsapp.py). The column
mapping below matches WhatsApp's macOS Core Data schema; if a real pull shows
different columns, this thin layer is where the fix goes.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .schema import Message

# WhatsApp stores timestamps as CFAbsoluteTime: seconds since 2001-01-01 UTC.
_CFTIME_EPOCH = 978307200


def _to_utc(cfabs: float | None) -> datetime:
    if cfabs is None:
        return datetime.fromtimestamp(0, timezone.utc)
    return datetime.fromtimestamp(cfabs + _CFTIME_EPOCH, timezone.utc)


# Sender name resolves in order: group-member contact name, then the member JID,
# then the push name on the message. For messages I sent, is_from_me is set and
# the sender label is "me".
_QUERY = """
SELECT
    m.Z_PK                         AS id,
    s.ZPARTNERNAME                 AS group_name,
    COALESCE(gm.ZCONTACTNAME, gm.ZMEMBERJID, m.ZPUSHNAME) AS sender,
    m.ZMESSAGEDATE                 AS ts,
    m.ZTEXT                        AS text,
    m.ZISFROMME                    AS is_from_me,
    mi.ZMEDIALOCALPATH             AS media_path
FROM ZWAMESSAGE m
JOIN ZWACHATSESSION s   ON s.Z_PK = m.ZCHATSESSION
LEFT JOIN ZWAGROUPMEMBER gm ON gm.Z_PK = m.ZGROUPMEMBER
LEFT JOIN ZWAMEDIAITEM   mi ON mi.Z_PK = m.ZMEDIAITEM
ORDER BY m.ZMESSAGEDATE ASC
"""


def read_messages(
    db_path: str, groups: list[str] | None = None
) -> list[Message]:
    """Return messages in chronological order, optionally filtered to groups.

    `db_path` must be a copy; opened read-only so a mistake can't write to it.
    """

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(_QUERY).fetchall()
    finally:
        conn.close()

    wanted = set(groups) if groups else None
    out: list[Message] = []
    for r in rows:
        group = r["group_name"] or "(unknown)"
        if wanted is not None and group not in wanted:
            continue
        is_from_me = bool(r["is_from_me"])
        out.append(
            Message(
                id=r["id"],
                group=group,
                sender="me" if is_from_me else (r["sender"] or "(unknown)"),
                ts=_to_utc(r["ts"]),
                text=r["text"] or "",
                is_from_me=is_from_me,
                media_path=r["media_path"],
            )
        )
    return out
