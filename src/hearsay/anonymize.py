"""Replace real senders with stable pseudonyms before any model sees a message.

Two reasons this exists and runs on the Mac, not in the model step:
  - the repo is public and the waiver licences its contents, so real names must
    never leave the machine;
  - the model reasons better about "FA" / "CR" / "FACULTY" than about names, and
    the trust step needs roles anyway.

A sender keeps the same label across the whole history (salted hash), so the
tracker can follow one person across messages. Known roles (my FA, the CR) are
pinned by a small local roster; everyone else becomes STUDENT-xxxx.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

from .schema import Message

# Per-machine salt so pseudonyms can't be reversed by guessing names. Loaded
# from the roster file in practice; a constant here keeps tests deterministic.
_DEFAULT_SALT = "hearsay-local"


def _pseudonym(name: str, salt: str) -> str:
    h = hashlib.sha256(f"{salt}:{name}".encode()).hexdigest()[:4]
    return f"STUDENT-{h}"


def anonymize(
    messages: list[Message],
    roster: dict[str, str] | None = None,
    salt: str = _DEFAULT_SALT,
) -> list[Message]:
    """Return messages with `sender` replaced by role or pseudonym.

    `roster` maps a real sender string to a pinned role, e.g.
    {"Dr Wilson": "FACULTY-OS", "Anmol": "CR"}. "me" is left as-is.
    """

    roster = roster or {}
    out: list[Message] = []
    for m in messages:
        if m.sender == "me":
            out.append(m)
            continue
        label = roster.get(m.sender) or _pseudonym(m.sender, salt)
        out.append(replace(m, sender=label))
    return out
