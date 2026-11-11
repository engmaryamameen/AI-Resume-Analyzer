"""Audit pinned packages; CPU wheel local version tags share the upstream torch advisories.

Run with the Python interpreter containing pip-audit, not the application's runtime interpreter.
This normalizes the advisory lookup only; installation keeps the exact CPU wheel lock.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    path = Path(sys.argv[1])
    packages = []
    for line in path.read_text().splitlines():
        if not line or line.startswith(("#", "-")):
            continue
        if line.startswith("torch=="):
            line = re.sub(r"\+cpu$", "", line)
        packages.append(line)
    with tempfile.TemporaryDirectory(prefix="resume-audit-") as directory:
        requirements = Path(directory) / "requirements.txt"
        requirements.write_text("\n".join(packages) + "\n")
        raise SystemExit(
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip_audit",
                    "--disable-pip",
                    "--no-deps",
                    "-r",
                    str(requirements),
                ]
            ).returncode
        )


if __name__ == "__main__":
    main()
