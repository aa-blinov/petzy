"""Run the browser checks one after another and say which failed.

    .venv/bin/python e2e/run.py            # all of them
    .venv/bin/python e2e/run.py share      # the ones with «share» in the name

They need the local stack up with the demo data (see e2e/README.md). Each check signs in once; a pause between them keeps under the
sign-in limit (5 a minute).
"""

import subprocess
import sys
import time
from pathlib import Path

here = Path(__file__).resolve().parent
only = sys.argv[1] if len(sys.argv) > 1 else ""
failed = []
checks = [p for p in sorted(here.glob("check_*.py")) if only in p.name]
for i, path in enumerate(checks):
    print(f"## {path.name}", flush=True)
    result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True)
    lines = [line for line in result.stdout.splitlines() if line.startswith(("PASS", "FAIL", "=="))]
    print("\n".join(lines) or result.stdout[-400:], flush=True)
    if (
        result.returncode != 0
        or any(line.startswith("FAIL") for line in lines)
        or not any("ALL PASS" in line for line in lines)
    ):
        failed.append(path.name)
        if result.returncode != 0:
            print(result.stderr[-600:])
    if i < len(checks) - 1:
        time.sleep(15)
print("\nFAILED: " + ", ".join(failed) if failed else "\nALL PASS")
sys.exit(1 if failed else 0)
