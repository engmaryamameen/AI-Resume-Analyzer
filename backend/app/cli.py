"""Operator commands: `python -m app.cli <command>`.

    grant-admin EMAIL   make an existing account an administrator (the only way to create one)
    maintenance         retention, orphan files, stuck jobs, expired sessions (schedule daily)
    verify-models       check the local model artifacts against the approved manifest
"""

import argparse
import json
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import normalise_email
from app.db.models import AuditEvent, User
from app.db.session import session_scope
from app.documents.storage import LocalPrivateStore
from app.maintenance import run_maintenance
from app.ml.artifacts import verify_manifest_files
from app.ml.manifest import load_manifest


def _grant_admin(email: str) -> int:
    with session_scope() as db:
        user = db.query(User).filter(User.email == normalise_email(email)).one_or_none()
        if user is None:
            print("No account with that email. Register it first, then grant the role.", file=sys.stderr)
            return 1
        user.role = "admin"
        db.add(AuditEvent(user_id=user.id, action="admin.granted", detail={"via": "cli"}))
    print("Administrator role granted.")
    return 0


def _maintenance() -> int:
    settings = get_settings()
    with session_scope() as db:
        result = run_maintenance(db, LocalPrivateStore(settings.storage_dir), settings)
    print(json.dumps(result, indent=2))
    return 0


def _verify_models() -> int:
    settings = get_settings()
    manifest = load_manifest(settings.model_dir)
    problems = verify_manifest_files(settings.model_dir, manifest)
    for problem in problems:
        print(problem, file=sys.stderr)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    grant = sub.add_parser("grant-admin")
    grant.add_argument("email")
    sub.add_parser("maintenance")
    sub.add_parser("verify-models")
    args = parser.parse_args(argv)
    if args.command == "grant-admin":
        return _grant_admin(args.email)
    if args.command == "maintenance":
        return _maintenance()
    return _verify_models()


if __name__ == "__main__":
    raise SystemExit(main())
