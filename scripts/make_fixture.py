"""Write a small SQLite DB shaped like WhatsApp's ChatStorage, for tests.

It mirrors only the columns ingest.read_messages reads. A few messages stand in
for the real traffic: a faculty date announcement, a student relay that
contradicts it, a worksheet notice, and pure chatter that prefilter must drop.

Usage:  python scripts/make_fixture.py tests/fixtures/chat.sqlite
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone

_CFTIME_EPOCH = 978307200


def _cfabs(iso: str) -> float:
    dt = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
    return dt.timestamp() - _CFTIME_EPOCH


def build(path: str) -> None:
    db = sqlite3.connect(path)
    c = db.cursor()
    c.executescript(
        """
        DROP TABLE IF EXISTS ZWAMESSAGE;
        DROP TABLE IF EXISTS ZWACHATSESSION;
        DROP TABLE IF EXISTS ZWAGROUPMEMBER;
        DROP TABLE IF EXISTS ZWAMEDIAITEM;

        CREATE TABLE ZWACHATSESSION (Z_PK INTEGER PRIMARY KEY, ZPARTNERNAME TEXT);
        CREATE TABLE ZWAGROUPMEMBER (Z_PK INTEGER PRIMARY KEY,
            ZCONTACTNAME TEXT, ZMEMBERJID TEXT);
        CREATE TABLE ZWAMEDIAITEM (Z_PK INTEGER PRIMARY KEY, ZMEDIALOCALPATH TEXT);
        CREATE TABLE ZWAMESSAGE (
            Z_PK INTEGER PRIMARY KEY, ZCHATSESSION INTEGER, ZGROUPMEMBER INTEGER,
            ZMEDIAITEM INTEGER, ZMESSAGEDATE REAL, ZTEXT TEXT,
            ZISFROMME INTEGER, ZPUSHNAME TEXT);
        """
    )

    c.executemany(
        "INSERT INTO ZWACHATSESSION (Z_PK, ZPARTNERNAME) VALUES (?, ?)",
        [(1, "DSA 2026"), (2, "AS1 UNOFFICIAL")],
    )
    c.executemany(
        "INSERT INTO ZWAGROUPMEMBER (Z_PK, ZCONTACTNAME, ZMEMBERJID) VALUES (?, ?, ?)",
        [
            (10, "Dr Wilson", "wilson@s.whatsapp.net"),
            (11, "Anmol CR", "anmol@s.whatsapp.net"),
            (12, "Random Classmate", "rc@s.whatsapp.net"),
        ],
    )

    rows = [
        # id, session, member, media, date, text, from_me, pushname
        (100, 1, 10, None, _cfabs("2026-10-13T04:30:00"),
         "OS FT-II (FJ2) on 29 Oct 2026, Units II & III, 50 marks.", 0, "Dr Wilson"),
        (101, 2, 12, None, _cfabs("2026-10-25T10:00:00"),
         "heard OS test moved to 30 Oct? not sure", 0, "Random Classmate"),
        (102, 1, 11, None, _cfabs("2026-10-21T09:49:00"),
         "DSA lab list: try to complete till 11th experiment", 0, "Anmol CR"),
        (103, 2, 12, None, _cfabs("2026-10-20T18:00:00"),
         "anyone free for lunch 🍕", 0, "Random Classmate"),
        (104, 1, None, None, _cfabs("2026-10-26T12:16:00"),
         "thanks sir", 1, "Me"),
    ]
    c.executemany(
        "INSERT INTO ZWAMESSAGE (Z_PK, ZCHATSESSION, ZGROUPMEMBER, ZMEDIAITEM,"
        " ZMESSAGEDATE, ZTEXT, ZISFROMME, ZPUSHNAME) VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    db.commit()
    db.close()
    print(f"wrote fixture: {path} ({len(rows)} messages)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/chat.sqlite")
