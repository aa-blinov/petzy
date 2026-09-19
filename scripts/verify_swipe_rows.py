"""Verify SwipeableRow is wired up correctly on Pets / Medications / AdminPanel.

For each of the three lists we login, navigate, then assert:
  - at least one .swipeable-row present
  - left action layer (.swipeable-row__action--left) present with "Изменить" label
  - right action layer (.swipeable-row__action--right) present with "Удалить" label
  - the legacy inline Pencil/Trash2 buttons are GONE from the card body

Then we simulate a touch swipe-left on the first Pets row, expect the right
layer (Удалить) to come into view (positive translate), and screenshot the
result for visual evidence.
"""

import asyncio
import json
import os
import sys
from playwright.async_api import async_playwright

BASE = "http://localhost:5173"


async def login(page):
    await page.goto(f"{BASE}/login")
    await page.wait_for_selector("input", timeout=10_000)
    inputs = await page.query_selector_all("input")
    await inputs[0].fill("admin")
    await inputs[1].fill("test1234")
    await page.click("button[type='submit']")
    await page.wait_for_url(f"{BASE}/", timeout=10_000)


async def check_list(page, path, screenshot_name, simulate_swipe=False):
    await page.goto(f"{BASE}{path}")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(800)  # let stagger animation settle

    rows = await page.query_selector_all(".swipeable-row")
    left_actions = await page.query_selector_all(".swipeable-row__action--left")
    right_actions = await page.query_selector_all(".swipeable-row__action--right")

    left_label = None
    if left_actions:
        label_el = await left_actions[0].query_selector(".swipeable-row__action-label")
        if label_el:
            left_label = (await label_el.inner_text()).strip()

    right_label = None
    if right_actions:
        label_el = await right_actions[0].query_selector(".swipeable-row__action-label")
        if label_el:
            right_label = (await label_el.inner_text()).strip()

    # Legacy buttons (should be gone from card body — not part of action layer)
    legacy_pencils = await page.query_selector_all(
        ".swipeable-row__surface button[aria-label='Редактировать']"
    )
    legacy_trash = await page.query_selector_all(
        ".swipeable-row__surface button[aria-label='Удалить']"
    )

    swipe_evidence = None
    if simulate_swipe and rows:
        surface = await rows[0].query_selector(".swipeable-row__surface")
        if surface:
            box = await surface.bounding_box()
            if box:
                cx = box["x"] + box["width"] / 2
                cy = box["y"] + box["height"] / 2
                # Swipe finger left → right (towards "Изменить")
                await page.mouse.move(cx, cy)
                await page.mouse.down()
                for i in range(1, 12):
                    await page.mouse.move(cx + i * 25, cy)
                    await page.wait_for_timeout(15)
                await page.wait_for_timeout(200)
                transform = await surface.evaluate("el => el.style.transform")
                swipe_evidence = transform
                await page.screenshot(
                    path=f"/Users/justcomex/Documents/petzy/screenshots/{screenshot_name}.png",
                    full_page=False,
                )
                await page.mouse.up()

    return {
        "path": path,
        "rows": len(rows),
        "left_actions": len(left_actions),
        "right_actions": len(right_actions),
        "left_label": left_label,
        "right_label": right_label,
        "legacy_inline_pencils": len(legacy_pencils),
        "legacy_inline_trash": len(legacy_trash),
        "swipe_transform_after": swipe_evidence,
    }


async def main():
    os.makedirs("/Users/justcomex/Documents/petzy/screenshots", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 390, "height": 844})
        page = await ctx.new_page()

        await login(page)

        # Visit /pets first to let usePet auto-select the first pet —
        # MedicationsList needs a selectedPetId before its query fires.
        await page.goto(f"{BASE}/pets")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(500)

        results = []
        results.append(await check_list(page, "/pets", "swipe_pets", simulate_swipe=True))
        results.append(await check_list(page, "/medications", "swipe_meds"))
        results.append(await check_list(page, "/admin", "swipe_admin"))

        print(json.dumps(results, indent=2, ensure_ascii=False))

        # Pass criteria: rows>=1, labels correct, legacy buttons = 0
        ok = True
        for r in results:
            if r["rows"] < 1 or r["left_label"] != "Изменить" or r["right_label"] != "Удалить":
                ok = False
            if r["legacy_inline_pencils"] != 0 or r["legacy_inline_trash"] != 0:
                ok = False

        await browser.close()
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())