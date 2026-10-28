"""Copy the live WhatsApp DB to a private local cache — the one FDA-gated step.

The dev shell has no Full Disk Access, so this is run by something that does
(me in a terminal with FDA granted, or the FDA-enabled sync process). It never
writes to the original: it copies the main DB plus its -wal/-shm sidecars so the
read is consistent, into private/ (gitignored). Then ingest reads the copy.

Usage:  python scripts/pull_whatsapp.py
Grant FDA once: System Settings → Privacy & Security → Full Disk Access →
enable your terminal app, then re-run.
"""

from __future__ import annotations

import os
import shutil
import sys

SRC_DIR = os.path.expanduser(
    "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared"
)
DST_DIR = os.path.join(os.path.dirname(__file__), "..", "private")
BASE = "ChatStorage.sqlite"


def main() -> int:
    os.makedirs(DST_DIR, exist_ok=True)
    copied = []
    for suffix in ("", "-wal", "-shm"):
        src = os.path.join(SRC_DIR, BASE + suffix)
        if not os.path.exists(src):
            continue
        dst = os.path.join(DST_DIR, BASE + suffix)
        try:
            shutil.copy2(src, dst)
            copied.append(BASE + suffix)
        except PermissionError:
            print(
                "Permission denied reading the WhatsApp DB.\n"
                "Grant Full Disk Access to this terminal and re-run:\n"
                "  System Settings → Privacy & Security → Full Disk Access",
                file=sys.stderr,
            )
            return 1
    if not copied:
        print("WhatsApp DB not found; is the Mac app installed?", file=sys.stderr)
        return 1
    print("copied:", ", ".join(copied), "->", os.path.abspath(DST_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
