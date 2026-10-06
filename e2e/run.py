"""Run the browser checks one after another and say which failed, and how long each took.

    .venv/bin/python e2e/run.py            # all of them
    .venv/bin/python e2e/run.py share      # the ones with «share» in the name

They need the local stack up with the demo data (see e2e/README.md). Each check signs in once.
A sign-in is allowed five times a minute per address, and every check comes from the same one,
so between them the runner asks the stand to put the counters back to zero
(POST /api/dev/reset-limits, local stand only) instead of waiting. An older stand without that
endpoint still needs the pause.
"""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

here = Path(__file__).resolve().parent
BASE = os.environ.get("PETZY_E2E_BASE", "http://localhost:3000")
only = sys.argv[1] if len(sys.argv) > 1 else ""


def _reset_limits() -> bool:
    """The stand's request counters back to zero. False when it has no such endpoint."""
    request = urllib.request.Request(BASE + "/api/dev/reset-limits", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return answer.status == 200
    except (urllib.error.URLError, OSError):
        return False


failed = []
took = []
checks = [p for p in sorted(here.glob("check_*.py")) if only in p.name]
can_reset = _reset_limits()
started_all = time.monotonic()
for i, path in enumerate(checks):
    if i:
        # No pause: the counters are what the pause was waiting for.
        if not (can_reset and _reset_limits()):
            time.sleep(15)
    started = time.monotonic()
    result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True)
    seconds = time.monotonic() - started
    took.append((seconds, path.name))
    lines = [line for line in result.stdout.splitlines() if line.startswith(("PASS", "FAIL", "==", "SKIP", "NOTE"))]
    print(f"## {path.name}  ({seconds:.1f}s)", flush=True)
    print("\n".join(lines) or result.stdout[-400:], flush=True)
    if (
        result.returncode != 0
        or any(line.startswith("FAIL") for line in lines)
        or not any("ALL PASS" in line for line in lines)
    ):
        failed.append(path.name)
        if result.returncode != 0:
            print(result.stderr[-600:])
print(f"\n== {len(checks)} checks in {time.monotonic() - started_all:.0f}s")
print("== slowest: " + ", ".join(f"{name} {seconds:.0f}s" for seconds, name in sorted(took, reverse=True)[:5]))
print("FAILED: " + ", ".join(failed) if failed else "ALL PASS")
sys.exit(1 if failed else 0)
