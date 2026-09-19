"""Profile every Petzy page.

Walks the dev stack at http://localhost:5173 with seeded credentials
(admin / test1234) and captures, for each route:

  - load + interactive timing (DOMContentLoaded, load, network idle)
  - Web Vitals (LCP, FCP, CLS) via PerformanceObserver
  - every console message (log/info/warn/error) with location
  - every uncaught page error / failed request
  - a mobile-viewport screenshot into screenshots/profile_<name>.png

Aggregates everything into a per-page summary printed at the end so we
can spot warning spam, slow renders, and broken routes at a glance.

Usage:  python3 scripts/profile_pages.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import (
    ConsoleMessage,
    Error as PWError,
    Page,
    Request,
    Response,
    TimeoutError as PWTimeout,
    sync_playwright,
)

FRONTEND = "http://localhost:5173"
USERNAME = "admin"
PASSWORD = "test1234"
OUTPUT_DIR = Path(__file__).parent.parent / "screenshots"
PROFILE_DIR = OUTPUT_DIR / "profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# Routes to profile. Order matches the user-visible navigation so any
# shared fetch errors cascade predictably.
ROUTES: list[tuple[str, str]] = [
    ("login",            "/login"),
    ("dashboard",        "/"),
    ("pets",             "/pets"),
    ("history_list",     "/history"),
    ("history_chart",    "/history?view=chart"),
    ("medications",      "/medications"),
    ("settings",         "/settings"),
    ("pet_form",         "/pets/new"),
    ("health_form",      "/form/feeding"),
    ("medication_form",  "/medications/new"),
    ("tiles_settings",   "/tiles-settings"),
    ("form_defaults",    "/form-defaults"),
    ("admin_panel",      "/admin"),
    ("user_form",        "/admin/users/new"),
]

# Web Vitals JS — LCP, FCP, CLS. Inlined because the page doesn't ship
# web-vitals.js as a runtime dependency.
VITALS_SCRIPT = """
() => new Promise((resolve) => {
  const out = { lcp: null, fcp: null, cls: 0, longTasks: 0 };
  const longTaskObs = new PerformanceObserver((list) => {
    for (const e of list.getEntries()) if (e.duration > 50) out.longTasks += 1;
  });
  try { longTaskObs.observe({ type: 'longtask', buffered: true }); } catch (_) {}

  const paintObs = new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      if (e.name === 'first-contentful-paint') out.fcp = e.startTime;
    }
  });
  try { paintObs.observe({ type: 'paint', buffered: true }); } catch (_) {}

  const lcpObs = new PerformanceObserver((list) => {
    const entries = list.getEntries();
    const last = entries[entries.length - 1];
    if (last) out.lcp = last.startTime;
  });
  try { lcpObs.observe({ type: 'largest-contentful-paint', buffered: true }); } catch (_) {}

  let cls = 0;
  const clsObs = new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      if (!e.hadRecentInput) cls += e.value;
    }
    out.cls = cls;
  });
  try { clsObs.observe({ type: 'layout-shift', buffered: true }); } catch (_) {}

  // Settle window: collect a final LCP/CLS after a short idle.
  setTimeout(() => {
    try { lcpObs.disconnect(); } catch (_) {}
    try { clsObs.disconnect(); } catch (_) {}
    try { paintObs.disconnect(); } catch (_) {}
    try { longTaskObs.disconnect(); } catch (_) {}
    resolve(out);
  }, 1500);
})
"""


@dataclass
class PageReport:
    name: str
    path: str
    status: str = "ok"
    load_ms: float | None = None
    network_idle_ms: float | None = None
    fcp_ms: float | None = None
    lcp_ms: float | None = None
    cls: float = 0.0
    long_tasks: int = 0
    console_errors: list[dict[str, Any]] = field(default_factory=list)
    console_warnings: list[dict[str, Any]] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    failed_requests: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "status": self.status,
            "timing_ms": {
                "load": self.load_ms,
                "network_idle": self.network_idle_ms,
            },
            "web_vitals": {
                "fcp_ms": self.fcp_ms,
                "lcp_ms": self.lcp_ms,
                "cls": self.cls,
                "long_tasks_gt_50ms": self.long_tasks,
            },
            "console": {
                "errors": self.console_errors,
                "warnings": self.console_warnings,
            },
            "page_errors": self.page_errors,
            "failed_requests": self.failed_requests,
            "note": self.note,
        }


def attach_listeners(page: Page, report: PageReport) -> list:
    """Wire console / error / request-failure listeners onto the page.

    Each listener appends to the report so the final summary contains
    everything that happened on that route. Returns the bound functions
    so the caller can detach them after profiling this route — without
    that, listeners from earlier routes would keep firing and pollute
    later reports.
    """
    def on_console(msg: ConsoleMessage) -> None:
        # Filter out HMR noise that isn't actionable.
        if msg.type == "error":
            report.console_errors.append({
                "text": msg.text[:300],
                "location": msg.location,
            })
        elif msg.type == "warning":
            # Skip the well-known dev-only noise.
            t = msg.text
            if "Download the React DevTools" in t:
                return
            report.console_warnings.append({
                "text": t[:300],
                "location": msg.location,
            })

    def on_pageerror(exc: PWError) -> None:
        report.page_errors.append(str(exc)[:400])

    def on_requestfailed(req: Request) -> None:
        report.failed_requests.append({
            "url": req.url,
            "method": req.method,
            "failure": req.failure,
        })

    def on_response(res: Response) -> None:
        # Track 4xx/5xx on API requests so we can distinguish auth
        # races from genuine backend errors.
        if res.status >= 400 and "/api/" in res.url:
            report.failed_requests.append({
                "url": res.url,
                "status": res.status,
            })

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("requestfailed", on_requestfailed)
    page.on("response", on_response)

    return [on_console, on_pageerror, on_requestfailed, on_response]


def profile_route(page: Page, name: str, path: str) -> PageReport:
    """Navigate to the route and collect one PageReport."""
    report = PageReport(name=name, path=path)
    listeners = attach_listeners(page, report)

    url = f"{FRONTEND}{path}"
    t0 = time.perf_counter()
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        dcl = (time.perf_counter() - t0) * 1000
        # If the response status is e.g. 5xx, flag it.
        if response and response.status >= 500:
            report.status = "http_5xx"
            report.note = f"HTTP {response.status}"
    except PWTimeout:
        report.status = "timeout"
        report.note = "DOMContentLoaded timed out"
        for fn in listeners:
            page.remove_listener("console", fn) if hasattr(fn, "__name__") and fn.__name__ == "on_console" else None
        return report

    try:
        page.wait_for_load_state("load", timeout=10_000)
        report.load_ms = round((time.perf_counter() - t0) * 1000, 1)
    except PWTimeout:
        report.load_ms = round((time.perf_counter() - t0) * 1000, 1)
        report.note = "load event timed out"

    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
        report.network_idle_ms = round((time.perf_counter() - t0) * 1000, 1)
    except PWTimeout:
        report.note = (report.note + "; networkidle timeout").strip("; ")

    # Let animations / late fetches settle before reading vitals.
    page.wait_for_timeout(800)

    try:
        vitals = page.evaluate(VITALS_SCRIPT)
        report.fcp_ms = round(vitals.get("fcp") or 0, 1) if vitals.get("fcp") else None
        report.lcp_ms = round(vitals.get("lcp") or 0, 1) if vitals.get("lcp") else None
        report.cls = round(vitals.get("cls") or 0, 4)
        report.long_tasks = int(vitals.get("longTasks") or 0)
    except Exception as e:
        report.note = (report.note + f"; vitals failed: {e}").strip("; ")

    # Screenshot for visual reference.
    try:
        page.screenshot(path=str(PROFILE_DIR / f"{name}.png"), full_page=False)
    except Exception:
        pass

    # Detach so the next route doesn't inherit our closures.
    for fn in listeners:
        try:
            if fn.__name__ == "on_console":
                page.remove_listener("console", fn)
            elif fn.__name__ == "on_pageerror":
                page.remove_listener("pageerror", fn)
            elif fn.__name__ == "on_requestfailed":
                page.remove_listener("requestfailed", fn)
            elif fn.__name__ == "on_response":
                page.remove_listener("response", fn)
        except Exception:
            pass

    return report


def main() -> int:
    reports: list[PageReport] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        )
        page = context.new_page()

        # Login first. Login is profiled as a separate route so we can
        # also see what warning chatter the auth flow produces.
        reports.append(profile_route(page, "login", "/login"))
        page.fill('input[placeholder="Введите имя пользователя"]', USERNAME)
        page.fill('input[placeholder="Введите пароль"]', PASSWORD)
        page.click('button[type="submit"]')
        try:
            page.wait_for_url(lambda url: not url.endswith("/login"), timeout=10_000)
        except PWTimeout:
            print("Login failed — dev server unreachable?", file=sys.stderr)
            return 2

        # Profile every other route. profile_route() detaches its own
        # listeners before returning, so successive calls stay isolated.
        for name, path in ROUTES[1:]:
            reports.append(profile_route(page, name, path))
            print(f"  profiled {name:18s} {path:32s} load={reports[-1].load_ms}ms "
                  f"err={len(reports[-1].console_errors)} warn={len(reports[-1].console_warnings)}")

        browser.close()

    # ---------- Summary ----------
    print("\n" + "=" * 78)
    print(f"{'route':20s} {'load(ms)':>9s} {'idle(ms)':>9s} {'FCP':>7s} {'LCP':>7s} {'CLS':>7s} {'err':>4s} {'warn':>5s}")
    print("-" * 78)
    for r in reports:
        print(f"{r.name:20s} "
              f"{(r.load_ms or 0):>9.0f} "
              f"{(r.network_idle_ms or 0):>9.0f} "
              f"{(r.fcp_ms or 0):>7.0f} "
              f"{(r.lcp_ms or 0):>7.0f} "
              f"{r.cls:>7.4f} "
              f"{len(r.console_errors):>4d} "
              f"{len(r.console_warnings):>5d}")

    # Surface anything noteworthy: errors, page errors, failed requests,
    # and the most common warning message per route.
    print("\n" + "=" * 78)
    print("Issues per route:")
    for r in reports:
        flagged = (
            r.console_errors or r.page_errors or r.failed_requests
            or r.status != "ok" or r.note
        )
        if not flagged:
            continue
        print(f"\n  [{r.name}]  {r.path}  ({r.note or 'ok'})")
        for e in r.console_errors[:3]:
            print(f"    console.error: {e['text'][:160]}")
        for e in r.page_errors[:3]:
            print(f"    pageerror:     {e[:160]}")
        for e in r.failed_requests[:3]:
            print(f"    req:           {e}")
        if r.status != "ok":
            print(f"    status:        {r.status}")

    # Most common warning texts — tells us where to focus cleanup.
    warning_counts: dict[str, int] = defaultdict(int)
    for r in reports:
        for w in r.console_warnings:
            warning_counts[w["text"][:120]] += 1
    if warning_counts:
        print("\n" + "=" * 78)
        print("Top warning messages (across all routes):")
        for text, count in sorted(warning_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {count:>3d}x  {text}")

    # Persist raw JSON for later diffing.
    json_path = PROFILE_DIR / "report.json"
    json_path.write_text(json.dumps(
        {"routes": [r.to_dict() for r in reports]},
        indent=2,
        ensure_ascii=False,
    ))
    print(f"\nFull JSON report → {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())