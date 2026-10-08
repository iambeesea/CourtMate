"""Operational commands.

    python -m app.manage make-admin someone@example.com
    python -m app.manage revoke-admin someone@example.com

Administrators can edit the sport catalog and verify venues. There is no way to
become one through the web app; the first administrator is created here.
"""

import sys

from sqlalchemy import select

from .db import session_factory
from .models import User


def set_role(email: str, role: str) -> int:
    with session_factory()() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            print(f"No account with the email {email}. Ask them to register first.")
            return 1
        if user.is_demo:
            print("Demo accounts cannot be changed.")
            return 1
        user.role = role
        db.commit()
        print(f"{user.email} is now {'an administrator' if role == 'admin' else 'a player'}.")
        return 0


def main(argv: list[str]) -> int:
    commands = {"make-admin": "admin", "revoke-admin": "player"}
    if len(argv) != 2 or argv[0] not in commands:
        print(__doc__)
        return 2
    return set_role(argv[1], commands[argv[0]])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
