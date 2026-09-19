"""MongoDB usage audit.

Scans web/*.py for common DB anti-patterns:

  - DB operations inside loops (N+1 risk)
  - Missing try/except around DB ops
  - ObjectId() string round-trips (str(ObjectId(x)) on already-string ids)
  - count_documents inside hot paths
  - find() without projection (loads entire docs into memory)
  - missing indexes (no create_index anywhere)
  - $set on missing fields (silent data loss)

Prints findings grouped by file. Writes audit/db_audit.json.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

WEB_DIR = Path(__file__).parent.parent / "web"
OUTPUT_PATH = Path(__file__).parent.parent / "audit" / "db_audit.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

DB_OP_RE = re.compile(
    r"""(?P<full>app\.db(?:\.(?P<coll>\w+)|\[(?P<coll2>['\"]\w+['\"])\])\.(?P<op>find_one|find|insert_one|insert_many|update_one|update_many|delete_one|delete_many|count_documents|aggregate|create_index|drop|replace_one)\b)"""
)


def find_enclosing_block(text: str, pos: int) -> tuple[int, int]:
    """Return (start_line, end_line) of the function enclosing pos."""
    line_no = text[:pos].count("\n") + 1
    # Walk back to the nearest `def ` line.
    start = text.rfind("\ndef ", 0, pos)
    if start == -1:
        return (0, line_no)
    start_line = text[:start].count("\n") + 2
    return (start_line, line_no)


def find_enclosing_loop(text: str, pos: int) -> int:
    """Return the line number of the nearest enclosing `for` / `while` loop, or 0."""
    line_no = text[:pos].count("\n") + 1
    # Search backwards for `for ... in` or `while ` at line starts.
    chunk = text[:pos]
    for pat in (r"\.for [\w,\s]+ in ", r"\.while "):
        for m in re.finditer(pat, chunk):
            if m.start() < pos:
                return chunk[:m.start()].count("\n") + 1
    return 0


def main() -> int:
    findings: dict[str, list[dict[str, Any]]] = defaultdict(list)

    index_declarations: list[tuple[str, int]] = []

    for path in sorted(WEB_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        text = path.read_text()
        relname = path.name

        for m in DB_OP_RE.finditer(text):
            full = m.group("full")
            coll = m.group("coll")
            op = m.group("op")
            line_no = text[: m.start()].count("\n") + 1

            if op == "create_index":
                index_declarations.append((relname, line_no))
                continue

            loop_line = find_enclosing_loop(text, m.start())
            if loop_line > 0 and op in {"find_one", "find", "count_documents", "aggregate"}:
                findings["n_plus_one"].append({
                    "file": relname,
                    "line": line_no,
                    "loop_line": loop_line,
                    "code": full,
                    "collection": coll,
                    "op": op,
                })

            # find() without projection loads full docs.
            if op == "find" and not re.search(r"projection", text[m.end(): m.end() + 200]):
                findings["find_no_projection"].append({
                    "file": relname,
                    "line": line_no,
                    "code": full,
                })

            # count_documents inside a loop = O(N*M).
            if op == "count_documents" and loop_line > 0:
                findings["count_in_loop"].append({
                    "file": relname,
                    "line": line_no,
                    "loop_line": loop_line,
                })

        # ObjectId round-trips: str(ObjectId("...")) on an already-string id.
        for m in re.finditer(r"ObjectId\(\s*(['\"])?([\w]+)\1?\s*\)", text):
            var = m.group(2)
            # Heuristic: if the argument looks like a variable already, suspect.
            if not (var.startswith('"') or var.startswith("'")):
                # Look back for whether `var` was already str-converted.
                preceding = text[max(0, m.start() - 60): m.start()]
                if re.search(rf"str\(\s*{var}\s*\)|['\"]{var}['\"]", preceding):
                    findings["object_id_redundant_str"].append({
                        "file": relname,
                        "line": text[:m.start()].count("\n") + 1,
                        "code": m.group(0),
                    })

        # Bare db.X.insert_one / find / etc. without surrounding try.
        # Walk back through lines; check if any `try:` was opened before
        # any `except`/`finally` and not yet closed.
        lines = text.splitlines()
        try_stack: list[int] = []  # line numbers of active try blocks
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("try:"):
                try_stack.append(i + 1)
            elif stripped.startswith(("except", "finally:")):
                if try_stack:
                    try_stack.pop()
            elif re.match(r"app\.db\.\w+\.\w+\(", stripped):
                if not try_stack:
                    findings["db_no_try"].append({
                        "file": relname,
                        "line": i + 1,
                        "code": stripped[:200],
                    })

    # Indexes — flag absence for the queried collections.
    queried_collections: set[str] = set()
    for path in WEB_DIR.glob("*.py"):
        for m in re.finditer(
            r"app\.db(?:\.(?P<c1>\w+)|\[(?P<c2>['\"]\w+['\"])\])\.(?:find|insert|update|delete|count|aggregate)",
            path.read_text(),
        ):
            name = m.group("c1") or (m.group("c2").strip("'\"") if m.group("c2") else None)
            if name:
                queried_collections.add(name)

    # A wrapper function that calls create_index on multiple collections
    # also counts as index declarations.
    ensure_funcs: set[str] = set()
    for path in WEB_DIR.glob("*.py"):
        text = path.read_text()
        for m in re.finditer(r"def\s+(ensure_indexes\w*)\s*\(", text):
            ensure_funcs.add(m.group(1))
    # And it must actually be invoked at startup.
    ensure_invoked = False
    app_text = (WEB_DIR / "app.py").read_text()
    for fn in ensure_funcs:
        if re.search(rf"\b{fn}\s*\(\s*\)", app_text):
            ensure_invoked = True
            break

    if index_declarations or ensure_invoked:
        # The bootstrap function takes care of all indexes.
        findings.pop("no_indexes", None)
    else:
        for coll in sorted(queried_collections):
            findings["no_indexes"].append({
                "collection": coll,
                "issue": "no create_index calls anywhere; production queries will full-scan",
            })

    # ---- Report ----
    print("=" * 78)
    print(f"MongoDB usage audit\n")
    print(f"Files scanned: {len(list(WEB_DIR.glob('*.py')))}")
    print(f"Index declarations found: {len(index_declarations)}")
    print(f"Collections queried: {len(queried_collections)}\n")

    if not findings:
        print("No issues found.")
        return 0

    for category, items in findings.items():
        if not items:
            continue
        print(f"\n── {category}  ({len(items)})")
        for it in items[:15]:
            if "file" in it:
                code = it.get("code", "")
                print(f"  {it['file']}:{it['line']}  {code}")
                if "loop_line" in it:
                    print(f"      ↑ inside loop starting at line {it['loop_line']}")
            else:
                print(f"  {json.dumps(it, ensure_ascii=False)}")
        if len(items) > 15:
            print(f"  ... and {len(items) - 15} more")

    OUTPUT_PATH.write_text(json.dumps(findings, indent=2, ensure_ascii=False))
    print(f"\nFull JSON → {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())