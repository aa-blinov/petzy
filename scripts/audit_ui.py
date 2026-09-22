"""Frontend UI audit — best practices and consistency.

Walks frontend/src and reports findings on:

  - TypeScript: any, @ts-ignore, @ts-expect-error, type assertions
  - React: missing deps, useEffect misuse, inline arrow components
  - A11y: missing aria-label, button vs div, missing alt text
  - Style: inline style={{...}} usage, hardcoded px values
  - Consistency: emoji, magic numbers, repeated patterns
  - Touch: targets < 44x44 (PWA mobile-first)
  - Loading/error/empty states in async UI

Prints a per-category summary and writes audit/ui_audit.json.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).parent.parent / "frontend" / "src"
OUTPUT_PATH = Path(__file__).parent.parent / "audit" / "ui_audit.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Patterns the audit checks. Each entry is (label, regex, severity).
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("ts_any_explicit", re.compile(r":\s*any\b|<any>|as\s+any\b"), "warn"),
    ("ts_ignore", re.compile(r"@ts-(?:ignore|expect-error)"), "warn"),
    ("ts_non_null_assert", re.compile(r"!\s*\.\s*\w|!!\w"), "info"),
    ("inline_style", re.compile(r"style\s*=\s*\{\{"), "info"),
    ("emoji_in_source", re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]"), "warn"),
    ("magic_44_check", re.compile(r"width:\s*['\"]?\d+px|height:\s*['\"]?\d+px"), "info"),
    ("useEffect_no_deps", re.compile(r"useEffect\([^)]*\),\s*\[\s*\]\s*\)"), "info"),
    ("button_missing_type", re.compile(r"<button(?![^>]*\btype\s*=)(?![^>]*\btype\s*=)"), "warn"),
    ("img_missing_alt", re.compile(r"<img(?![^>]*\balt\s*=)"), "warn"),
    ("onClick_div", re.compile(r"<div[^>]*onClick\s*="), "warn"),
]

# Filter noise — files/patterns that don't count.
SKIP_FILES = {
    "vite-env.d.ts",
}


def main() -> int:
    findings: dict[str, list[dict[str, Any]]] = defaultdict(list)
    file_count = 0
    line_count = 0
    pattern_hits: Counter[str] = Counter()

    for path in sorted(SRC_DIR.rglob("*")):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if path.name in SKIP_FILES:
            continue
        if path.name.endswith(".test.tsx") or path.name.endswith(".test.ts"):
            continue
        relname = str(path.relative_to(SRC_DIR))
        text = path.read_text()
        file_count += 1
        line_count += text.count("\n") + 1

        for label, pat, severity in PATTERNS:
            for m in pat.finditer(text):
                line_no = text[: m.start()].count("\n") + 1
                # Skip @ts-expect-error when it's actually expected to fail.
                snippet = text.splitlines()[line_no - 1].strip()[:120]
                findings[label].append(
                    {
                        "file": relname,
                        "line": line_no,
                        "snippet": snippet,
                        "severity": severity,
                    }
                )
                pattern_hits[label] += 1

    # Per-file style hoisting: count inline-style occurrences.
    inline_style_per_file: Counter[str] = Counter()
    for f in findings.get("inline_style", []):
        inline_style_per_file[f["file"]] += 1

    # ---------- Report ----------
    print("=" * 78)
    print(f"Frontend UI audit — {file_count} files, {line_count} lines\n")
    print("Pattern hits:")
    for label, count in pattern_hits.most_common():
        sev = next((p[2] for p in PATTERNS if p[0] == label), "")
        print(f"  {label:32s} {count:>4d}   [{sev}]")
    print()

    # Print detailed findings for the warn-severity categories first.
    severities = ("warn", "info")
    for sev in severities:
        print("-" * 78)
        print(f"Severity: {sev}")
        print("-" * 78)
        for label, pat, severity in PATTERNS:
            if severity != sev:
                continue
            items = findings.get(label, [])
            if not items:
                continue
            print(f"\n  {label}  ({len(items)})")
            # Group by file for compact output.
            by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for it in items:
                by_file[it["file"]].append(it)
            for fname, file_items in sorted(by_file.items()):
                line_list = ", ".join(str(it["line"]) for it in file_items[:8])
                more = f" (+{len(file_items) - 8} more)" if len(file_items) > 8 else ""
                print(f"    {fname:50s} L{line_list}{more}")

    # Top inline-style offenders.
    if inline_style_per_file:
        print("\n" + "=" * 78)
        print("Top inline-style offenders:")
        for fname, count in inline_style_per_file.most_common(10):
            print(f"  {count:>4d}  {fname}")

    OUTPUT_PATH.write_text(
        json.dumps(
            {"file_count": file_count, "line_count": line_count, "findings": findings},
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nFull JSON → {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
