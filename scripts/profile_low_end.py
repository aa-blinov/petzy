"""Profile the app under mid-tier Android conditions.

Baseline (scripts/profile_pages.py) measures on a desktop viewport with
no throttling. Real Samsung A-series / Redmi Note devices are slower:

  - CPU  ~3-4× slower than iPhone 13
  - Network often falls back to 3G/edge in elevators, cafes, transit

This script:
  - viewport 360×640 (Android phone, smaller than the 390×844 iPhone)
  - CPU throttling 4× via CDP Emulation.setCPUThrottlingRate
  - Network "Slow 4G" via CDP (1.6 Mbps down, 750 Kbps up, 150 ms RTT)
  - Samsung Galaxy A-series user agent
  - 1 round cold + 1 round warm per route (warm = service-worker cached)
  - runs against `vite preview` (production build) so Cache-Control /
    service-worker precache actually work — vite dev always returns
    fresh module sources and would make the warm round meaningless

Reports FCP / LCP / CLS / load time per route + 2 screenshots per
route (cold + warm) for visual diff vs baseline.
"""

import asyncio
import json
import os
import statistics
import sys
from pathlib import Path

from playwright.async_api import async_playwright

# vite preview serves the built bundle; backend on :5001 stays separate.
FRONTEND = os.environ.get("PETZY_FRONTEND", "http://localhost:4173")
BACKEND = os.environ.get("PETZY_BACKEND", "http://localhost:5001")
OUTPUT_DIR = Path(__file__).parent.parent / "audit"
SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots" / "low_end"

# Routes that actually do meaningful work (skip login which is auth-only).
ROUTES = [
    ("dashboard", "/"),
    ("pets", "/pets"),
    ("history", "/history"),
    ("medications", "/medications"),
    ("admin_panel", "/admin"),
]


async def _apply_throttling(context, page):
    """Set CPU 4× and Slow 4G via Chrome DevTools Protocol."""
    client = await context.new_cdp_session(page)
    await client.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    await client.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "latency": 150,           # ms RTT
            "downloadThroughput": 1.6 * 1024 * 1024 / 8,   # 1.6 Mbps → bytes/s
            "uploadThroughput": 0.75 * 1024 * 1024 / 8,    # 750 Kbps → bytes/s
        },
    )


async def _proxy_api_to_backend(context):
    """vite preview doesn't proxy /api → backend. Route requests manually."""

    async def handle(route):
        url = route.request.url
        # Anything that's not a frontend asset — proxy to backend
        if "/api/" in url or "/uploads/" in url:
            target = url.replace(FRONTEND, BACKEND)
            method = route.request.method
            headers = {
                k: v
                for k, v in route.request.headers.items()
                if k.lower() not in {"host", "content-length"}
            }
            post_data = route.request.post_data
            try:
                resp = await context.request.fetch(
                    target, method=method, headers=headers, data=post_data
                )
                body = await resp.body()
                await route.fulfill(
                    status=resp.status,
                    headers={
                        k: v
                        for k, v in resp.headers.items()
                        if k.lower()
                        not in {"content-encoding", "transfer-encoding", "content-length"}
                    },
                    body=body,
                )
            except Exception as e:
                await route.fulfill(status=502, body=f"proxy error: {e}".encode())
        else:
            await route.continue_()

    return handle


async def _measure(page):
    """Return (FCP, LCP, CLS, loadMs) for the current page."""
    # Wait for load event before sampling
    await page.evaluate(
        """() => new Promise((resolve) => {
            if (document.readyState === 'complete') resolve();
            else window.addEventListener('load', () => resolve(), {once: true});
        })"""
    )

    metrics = await page.evaluate(
        """async () => {
            // Wait a bit for LCP to settle (LCP can update after FCP)
            await new Promise(r => setTimeout(r, 500));

            const fcpEntry = performance.getEntriesByName('first-contentful-paint')[0];
            const fcp = fcpEntry ? fcpEntry.startTime : null;

            // LCP via PerformanceObserver (buffered)
            const lcp = await new Promise((resolve) => {
                let lastLcp = null;
                const po = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        lastLcp = entry.startTime;
                    }
                });
                try {
                    po.observe({type: 'largest-contentful-paint', buffered: true});
                } catch (e) { /* not supported */ }
                // Also read buffered entries synchronously
                const buffered = performance.getEntriesByType('largest-contentful-paint');
                if (buffered.length) lastLcp = buffered[buffered.length - 1].startTime;
                setTimeout(() => resolve(lastLcp), 100);
            });

            // CLS
            let cls = 0;
            const ls = performance.getEntriesByType('layout-shift') || [];
            for (const e of ls) {
                if (!e.hadRecentInput) cls += e.value;
            }

            const nav = performance.getEntriesByType('navigation')[0];
            const loadMs = nav ? nav.loadEventEnd - nav.startTime : null;

            return { fcp, lcp, cls, loadMs };
        }"""
    )
    return metrics


async def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 360, "height": 640},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (Linux; Android 13; SM-A145F) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            ),
        )
        page = await context.new_page()
        await _apply_throttling(context, page)
        # Proxy /api/* to the Flask backend (vite preview has no dev proxy).
        await context.route("**/*", await _proxy_api_to_backend(context))

        # Login once (under throttle too — real users authenticate under load)
        # First cold load is heavy under CPU 4× — Vite dev serves each module
        # on demand; give it a generous timeout.
        await page.goto(f"{FRONTEND}/login", wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_selector("input", timeout=60000)
        inputs = await page.query_selector_all("input")
        await inputs[0].fill("admin")
        await inputs[1].fill("test1234")
        await page.click("button[type='submit']")
        await page.wait_for_url(lambda u: not u.endswith("/login"), timeout=60000)

        results = []
        for name, path in ROUTES:
            row = {"route": name, "path": path, "cold": None, "warm": None}
            # Cold: drop cache via cache-buster query string and measure
            cache_buster = f"?_t={os.urandom(4).hex()}"
            t0 = asyncio.get_event_loop().time()
            await page.goto(f"{FRONTEND}{path}{cache_buster}", wait_until="domcontentloaded")
            row["cold"] = await _measure(page)
            cold_total_ms = (asyncio.get_event_loop().time() - t0) * 1000
            row["cold"]["total_ms"] = round(cold_total_ms, 1)
            await page.screenshot(path=str(SCREENSHOTS_DIR / f"{name}_cold.png"))

            # Warm: same path, served from HTTP cache (no cache-buster)
            t0 = asyncio.get_event_loop().time()
            await page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded")
            row["warm"] = await _measure(page)
            warm_total_ms = (asyncio.get_event_loop().time() - t0) * 1000
            row["warm"]["total_ms"] = round(warm_total_ms, 1)
            await page.screenshot(path=str(SCREENSHOTS_DIR / f"{name}_warm.png"))
            results.append(row)

            print(
                f"  {name:12s}  cold LCP={row['cold']['lcp']:.0f}ms "
                f"FCP={row['cold']['fcp']:.0f}ms  |  "
                f"warm LCP={row['warm']['lcp']:.0f}ms FCP={row['warm']['fcp']:.0f}ms"
            )

        await browser.close()

        # Aggregate
        cold_lcp = [r["cold"]["lcp"] for r in results if r["cold"]["lcp"]]
        warm_lcp = [r["warm"]["lcp"] for r in results if r["warm"]["lcp"]]
        cold_cls = [r["cold"]["cls"] for r in results if r["cold"]["cls"] is not None]
        summary = {
            "conditions": {
                "viewport": "360x640 @2x",
                "device_scale_factor": 2,
                "user_agent": "Samsung SM-A145F (Galaxy A14)",
                "cpu_throttling": "4x slowdown",
                "network": "Slow 4G (1.6 Mbps down / 750 Kbps up / 150 ms RTT)",
            },
            "routes": results,
            "aggregate": {
                "cold_lcp_p50_ms": round(statistics.median(cold_lcp), 1) if cold_lcp else None,
                "cold_lcp_p95_ms": round(sorted(cold_lcp)[int(len(cold_lcp) * 0.95) - 1], 1)
                if len(cold_lcp) >= 2
                else (cold_lcp[0] if cold_lcp else None),
                "warm_lcp_p50_ms": round(statistics.median(warm_lcp), 1) if warm_lcp else None,
                "warm_lcp_p95_ms": round(sorted(warm_lcp)[int(len(warm_lcp) * 0.95) - 1], 1)
                if len(warm_lcp) >= 2
                else (warm_lcp[0] if warm_lcp else None),
                "cls_max": max(cold_cls) if cold_cls else None,
            },
        }

        out_path = OUTPUT_DIR / "low_end_profile.json"
        out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        print(f"\nReport → {out_path}")
        print(
            f"\nCold  LCP p50={summary['aggregate']['cold_lcp_p50_ms']}ms "
            f"p95={summary['aggregate']['cold_lcp_p95_ms']}ms"
        )
        print(
            f"Warm  LCP p50={summary['aggregate']['warm_lcp_p50_ms']}ms "
            f"p95={summary['aggregate']['warm_lcp_p95_ms']}ms"
        )

        # Pass criteria: warm LCP p95 < 2500ms (Google "Good" threshold for 4G).
        ok = summary["aggregate"]["warm_lcp_p95_ms"] is not None and \
             summary["aggregate"]["warm_lcp_p95_ms"] < 2500
        print(f"\nVerdict: {'PASS' if ok else 'NEEDS WORK'} (warm p95 < 2500ms)")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))