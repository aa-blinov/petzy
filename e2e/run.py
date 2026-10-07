"""Run the browser checks one after another and say which failed, and how long each took.

    .venv/bin/python e2e/run.py            # all of them
    .venv/bin/python e2e/run.py share      # the ones with «share» in the name

They need the local stack up with the demo data (see e2e/README.md). Each check signs in once.
A sign-in is allowed five times a minute per address, and every check comes from the same one,
so between them the runner asks the stand to put the counters back to zero
(POST /api/dev/reset-limits, local stand only) instead of waiting. An older stand without that
endpoint still needs the pause.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from seed_demo import DEMO_PASSWORD  # noqa: E402

here = Path(__file__).resolve().parent
BASE = os.environ.get("PETZY_E2E_BASE", "http://localhost:3000")
only = sys.argv[1] if len(sys.argv) > 1 else ""

# The names the checks make their throwaway pets under (check_weight, check_record_save and the
# rest). Anything else on the stand was put there by a person and is none of the runner's business.
SCRATCH = ("Тест-М", "Тест-М-2", "Тест-К")


def _reset_limits() -> bool:
    """The stand's request counters back to zero. False when it has no such endpoint."""
    request = urllib.request.Request(BASE + "/api/dev/reset-limits", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return answer.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _clean_scratch() -> list[str]:
    """The throwaway pets a check left behind, removed before anything runs.

    Most checks make their own «Тест-М» and then take the first pet of that name off the server,
    so one leftover is enough: every run after it measures a pet from an earlier run and leaves
    its own behind instead. That stale pet has already failed a run of check_card_gaps twice,
    for a reason that had nothing to do with the check. Returns what it removed, for the log.

    The sign-in is over HTTP with the returned token rather than through the browser: the runner
    is already outside one, and the stand's five sign-ins a minute are the checks' to spend."""
    token = None

    def call(method: str, path: str, body=None):
        nonlocal token
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(BASE + "/api" + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=15) as answer:
            got = json.loads(answer.read() or b"{}")
            if isinstance(got, dict) and got.get("access_token"):
                token = got["access_token"]
            return got

    try:
        call("POST", "/auth/login", {"username": "demo", "password": DEMO_PASSWORD})
        pets = call("GET", "/pets").get("pets", [])
    except (urllib.error.URLError, OSError, ValueError):
        return []  # the stand is not up yet: the checks will say so themselves, with a better message
    removed = []
    for pet in pets:
        if pet.get("name") in SCRATCH:
            call("DELETE", f"/pets/{pet['_id']}")
            removed.append(pet["name"])
    return removed


failed = []
took = []
checks = [p for p in sorted(here.glob("check_*.py")) if only in p.name]
can_reset = _reset_limits()
leftover = _clean_scratch()
if leftover:
    print("== убраны питомцы, оставшиеся от прошлого прогона: " + ", ".join(leftover), flush=True)
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
