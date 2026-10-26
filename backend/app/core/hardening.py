"""Process-level hardening for the worker.

`PR_SET_DUMPABLE=0` makes /proc/<pid>/environ and /proc/<pid>/mem unreadable to other processes of the
same user, in particular to the extraction child, which would otherwise be able to read the worker's
database URL and secret key. This is defence in depth on Linux; the real boundary is the container the
worker runs in (see docs/INFERENCE_AND_DEPLOYMENT.md).
"""

import ctypes
import sys

_PR_SET_DUMPABLE = 4


def harden_process() -> None:
    if not sys.platform.startswith("linux"):
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_DUMPABLE) failed")
