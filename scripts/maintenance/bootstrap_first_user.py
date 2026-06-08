"""Create the first local user account for an empty SIMVal database."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import json
import secrets

from app.backend.api.database import sqlite_connection_scope
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount
from app.backend.operations.user_bootstrap import bootstrap_first_user


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-path", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--role",
        action="append",
        choices=[role.value for role in Role],
        default=None,
        help="May be supplied multiple times. Defaults to admin.",
    )
    parser.add_argument("--signature-label")
    parser.add_argument("--software-version", required=True)
    parser.add_argument("--issue-session", action="store_true")
    parser.add_argument("--session-id")
    parser.add_argument("--session-hours", type=int, default=12)
    parser.add_argument("--evidence-output")
    args = parser.parse_args(argv)

    if args.session_hours < 1:
        raise SystemExit("--session-hours must be at least 1")
    issue_session = args.issue_session or args.session_id is not None
    timestamp = datetime.now(timezone.utc)
    roles = tuple(Role(value) for value in (args.role or [Role.ADMIN.value]))
    user = UserAccount(
        id=args.user_id,
        display_name=args.display_name,
        email=args.email,
        roles=roles,
        signature_label=args.signature_label,
        created_at=timestamp,
    )
    session_id = None
    session_expires_at = None
    if issue_session:
        session_id = args.session_id or secrets.token_urlsafe(32)
        session_expires_at = timestamp + timedelta(hours=args.session_hours)

    with sqlite_connection_scope(Path(args.database_path)) as connection:
        evidence = bootstrap_first_user(
            connection=connection,
            user=user,
            software_version=args.software_version,
            timestamp=timestamp,
            session_id=session_id,
            session_expires_at=session_expires_at,
        )

    payload = json.dumps(evidence.to_payload(), indent=2, sort_keys=True) + "\n"
    if args.evidence_output:
        output_path = Path(args.evidence_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

