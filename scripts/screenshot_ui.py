"""Take mobile-viewport screenshots of every Petzy screen.

Uses Playwright with the system Google Chrome so we don't have to wait
for the Chromium download. Runs against a local Docker stack
(docker-compose.local.yml, nginx on 127.0.0.1:3001) with seeded demo data
(demo / petzy-demo-2026), on an iPhone Pro Max viewport (430x932).

The color scheme is pinned at the browser context level (dark by default)
so captures are deterministic — the app reads prefers-color-scheme and sets
data-prefers-color-scheme on <html>. Override with PETZY_SHOT_THEME=light
(or system) if a light-theme run is wanted.

The admin pages are captured as a second user: the admin is whoever
ADMIN_USERNAME names, never the demo user. Start the stack with
docker-compose.demo-admin.yml (see its header) so «demo_admin» signs in with
the demo password, or pass PETZY_SHOT_ADMIN_USER / PETZY_SHOT_ADMIN_PASS.

Override the target and login with PETZY_SHOT_BASE, PETZY_SHOT_USER,
PETZY_SHOT_PASS if the stack lives elsewhere.

Saves screenshots into screenshots/ for inspection.
"""

import os
import sys
from pathlib import Path
from typing import Literal

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

FRONTEND = os.environ.get("PETZY_SHOT_BASE", "http://127.0.0.1:3001")
OUTPUT_DIR = Path(os.environ.get("PETZY_SHOT_OUT", Path(__file__).parent.parent / "screenshots"))
USERNAME = os.environ.get("PETZY_SHOT_USER", "demo")
PASSWORD = os.environ.get("PETZY_SHOT_PASS", "petzy-demo-2026")
ADMIN_USERNAME = os.environ.get("PETZY_SHOT_ADMIN_USER", "demo_admin")
ADMIN_PASSWORD = os.environ.get("PETZY_SHOT_ADMIN_PASS", PASSWORD)

ColorScheme = Literal["dark", "light", "no-preference", "null"]
COLOR_SCHEME: ColorScheme = os.environ.get("PETZY_SHOT_THEME", "dark")  # type: ignore[assignment]

# Screens to capture after login. Order matters — Dashboard first.
SCREENS = [
    # Top-level pages
    ("dashboard", "/"),
    ("pets", "/pets"),
    ("history", "/history"),
    ("medications", "/medications"),
    ("settings", "/settings"),
    # Form screens
    ("pet_form", "/pets/new"),
    ("health_form", "/form/feeding"),
    ("medication_form", "/medications/new"),
    # Settings sub-pages
    ("tiles_settings", "/tiles-settings"),
    ("form_defaults", "/form-defaults"),
]

# Captured signed in as the admin, in a context of their own.
ADMIN_SCREENS = [
    ("admin_panel", "/admin"),
    ("user_form", "/admin/users/new"),
]

VIEWPORT = {"width": 430, "height": 932}
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
    "Mobile/15E148 Safari/604.1"
)


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        # iPhone 14/15/16 Pro Max viewport: 430x932 logical pixels.
        browser = pw.chromium.launch(
            channel="chrome",
            headless=True,
        )
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            color_scheme=COLOR_SCHEME,
            user_agent=USER_AGENT,
        )
        page = context.new_page()

        # Login first.
        page.goto(f"{FRONTEND}/login", wait_until="networkidle")
        page.screenshot(path=str(OUTPUT_DIR / "00_login.png"), full_page=False)

        page.fill('input[placeholder="Введите логин"]', USERNAME)
        page.fill('input[placeholder="Введите пароль"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url(lambda url: not url.endswith("/login"), timeout=10_000)

        # Capture each screen.
        for name, path in SCREENS:
            page.goto(f"{FRONTEND}{path}", wait_until="networkidle")
            # Wait for layout to settle.
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUTPUT_DIR / f"{name}.png"), full_page=False)
            print(f"  captured {name} ({path})")

        # Bonus: capture the QuickAdd bottom sheet by tapping the FAB.
        page.goto(f"{FRONTEND}/", wait_until="networkidle")
        page.wait_for_timeout(1500)
        # A plain click works: the FAB is a real button (app-fab) in a portal.
        # The old antd FloatingBubble div (adm-floating-bubble-button) is gone.
        page.click(".app-fab")
        # QuickAddSheet is rendered as antd-mobile Popup. Wait for the sheet's
        # heading rather than the popup container — the spring-animated popup
        # body is sometimes flagged "hidden" by Playwright's checks even when
        # it's actually rendered and visible to the user.
        page.wait_for_selector("text=Что записать?", timeout=5_000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUTPUT_DIR / "quick_add_sheet.png"), full_page=False)
        print("  captured quick_add_sheet (FAB sheet)")

        # Bonus: capture History swipe gestures (left=delete, right=edit).
        # useSwipeableRow listens to Pointer Events, not touch events, so we
        # dispatch pointerdown/pointermove and stop before pointerup — the row
        # stays mid-drag (transform applied) and the action layer is visible.
        page.goto(f"{FRONTEND}/history", wait_until="networkidle")
        page.wait_for_timeout(1500)

        row_box = page.evaluate("""() => {
            const el = document.querySelector('.swipeable-row__surface');
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { x: r.x, y: r.y, w: r.width, h: r.height, midY: r.y + r.height / 2 };
        }""")
        if row_box:
            mid_y = row_box["midY"]

            def swipe(from_x: int, step: int) -> None:
                page.evaluate(
                    """({y, fromX, step}) => {
                        const el = document.querySelector('.swipeable-row__surface');
                        if (!el) return;
                        const opts = (x) => ({
                            bubbles: true, cancelable: true, pointerId: 1,
                            pointerType: 'touch', isPrimary: true,
                            clientX: x, clientY: y, buttons: 1,
                        });
                        el.dispatchEvent(new PointerEvent('pointerdown', opts(fromX)));
                        for (let i = 1; i <= 12; i++) {
                            el.dispatchEvent(new PointerEvent('pointermove', opts(fromX + i * step)));
                        }
                        // No pointerup: pause mid-drag so the action layer
                        // stays revealed in the screenshot.
                    }""",
                    {"y": mid_y, "fromX": from_x, "step": step},
                )
                page.wait_for_timeout(400)

            # Right-swipe (left→right finger motion) — reveals Edit action.
            swipe(40, 7)
            page.screenshot(path=str(OUTPUT_DIR / "history_swipe_right.png"), full_page=False)
            print("  captured history_swipe_right (edit reveal)")

            # Reset, then left-swipe (delete reveal).
            page.goto(f"{FRONTEND}/history", wait_until="networkidle")
            page.wait_for_timeout(1500)
            swipe(350, -7)
            page.screenshot(path=str(OUTPUT_DIR / "history_swipe_left.png"), full_page=False)
            print("  captured history_swipe_left (delete reveal)")

        # The admin pages, signed in as the admin (a separate context: the
        # demo user's session must not be replaced for the shots above).
        admin_context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            color_scheme=COLOR_SCHEME,
            user_agent=USER_AGENT,
        )
        admin_page = admin_context.new_page()
        admin_page.goto(f"{FRONTEND}/login", wait_until="networkidle")
        admin_page.fill('input[placeholder="Введите логин"]', ADMIN_USERNAME)
        admin_page.fill('input[placeholder="Введите пароль"]', ADMIN_PASSWORD)
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_url(lambda url: not url.endswith("/login"), timeout=10_000)
        # A new account is asked for its consent once, a moment after the
        # page opens; accept it so the dialog doesn't sit over the admin pages.
        consent = admin_page.get_by_text("Даю согласие", exact=True)
        try:
            consent.wait_for(timeout=4_000)
            consent.click()
            admin_page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            pass  # the account had already given it
        for name, path in ADMIN_SCREENS:
            admin_page.goto(f"{FRONTEND}{path}", wait_until="networkidle")
            admin_page.wait_for_timeout(800)
            admin_page.screenshot(path=str(OUTPUT_DIR / f"{name}.png"), full_page=False)
            print(f"  captured {name} ({path}, as {ADMIN_USERNAME})")

        browser.close()

    print(f"\nScreenshots saved to {OUTPUT_DIR}")
    for f in sorted(OUTPUT_DIR.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name:20s}  {size // 1024:5d} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
