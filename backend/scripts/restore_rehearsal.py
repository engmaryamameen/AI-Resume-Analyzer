"""Backup a disposable DB, restore into a fresh DB, compare rows and content, then remove the restore.

Requires ALLOW_DISPOSABLE_RESTORE=1 and TEST_DATABASE_URL. Never changes the source schema.
Encryption/retention of production backups is an operator-managed control, not simulated here.
"""

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


def main():
    if os.environ.get("ALLOW_DISPOSABLE_RESTORE") != "1":
        raise SystemExit("Set ALLOW_DISPOSABLE_RESTORE=1 for a disposable database only")
    url = make_url(os.environ["TEST_DATABASE_URL"])
    if not url.database or "test" not in url.database:
        raise SystemExit("Source database name must contain test")
    restore_name = f"review_restore_{uuid.uuid4().hex[:12]}"
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    connection = [
        "-h",
        url.host or "localhost",
        "-p",
        str(url.port or 5432),
        "-U",
        url.username or "postgres",
    ]

    def run(command, *args):
        binary = shutil.which(command) or f"/usr/lib/postgresql/18/bin/{command}"
        subprocess.run([binary, *connection, *args], env=env, check=True, capture_output=True)

    def counts(engine):
        with engine.connect() as db:
            return {
                table: {
                    "rows": db.scalar(text(f'SELECT count(*) FROM "{table}"')),
                    "digest": db.scalar(
                        text(
                            f"SELECT md5(COALESCE(string_agg(row_to_json(t)::text, E'\\n' ORDER BY row_to_json(t)::text), '')) FROM \"{table}\" t"
                        )
                    ),
                }
                for table in sorted(inspect(engine).get_table_names())
            }

    source = create_engine(url)
    target = create_engine(url.set(database=restore_name))
    try:
        with tempfile.TemporaryDirectory(prefix="resume-restore-") as directory:
            dump = str(Path(directory) / "backup.dump")
            run("pg_dump", "-Fc", "--no-owner", "-d", url.database, "-f", dump)
            run("createdb", restore_name)
            run("pg_restore", "--no-owner", "--exit-on-error", "-d", restore_name, dump)
            before, after = counts(source), counts(target)
            if before != after:
                raise SystemExit("Restored rows or content differ")
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "source_tables": before,
                        "restored_tables": after,
                        "scope": "disposable database logical restore; file-volume restore and encrypted backup recovery require staging",
                    }
                )
            )
    finally:
        source.dispose()
        target.dispose()
        run("dropdb", "--if-exists", restore_name)


if __name__ == "__main__":
    main()
