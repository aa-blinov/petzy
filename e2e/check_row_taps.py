"""A tap on a button inside a swipeable row still counts as a tap when the finger drifts a few pixels.

A horizontal drift of 4 px locked the row as a swipe, and the click that followed was swallowed: «Пополнить» and
«Дали сейчас» on a medicine course did nothing for a finger that moved sideways. A real swipe still swallows its click,
so it does not open the course.
"""

import asyncio
import re

from common import BASE, api, async_playwright, check, login, new_page, summary

COURSE = "Тест-Касание"
TITLE = "Пополнить остаток"


async def tap(cdp, x, y, drift=0):
    """A finger touches (x, y), moves sideways by `drift` px, and lifts."""
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    if drift:
        for step in (drift / 2, drift):
            await cdp.send(
                "Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x + step, "y": y + 1}]}
            )
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


async def centre(locator):
    await locator.scroll_into_view_if_needed()
    box = await locator.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(browser, sw=False)
        await login(pg)
        made = await api(pg, "POST", "/pets", {"name": "Тест-М", "species": "dog", "gender": "male"})
        pid = ((made["json"] or {}).get("pet") or {}).get("_id")
        try:
            # The list shows the selected pet's courses, so the throwaway pet is selected first.
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); "
                "localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, "Тест-М"],
            )
            await api(
                pg,
                "POST",
                "/medications",
                {
                    "pet_id": pid,
                    "name": COURSE,
                    "type": "Таблетка",
                    "default_dose": 1,
                    "dose_unit": "таб",
                    "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["23:58"]},
                    "inventory_enabled": True,
                    "inventory_current": 5,
                    "is_active": True,
                },
            )
            cdp = await ctx.new_cdp_session(pg)
            await pg.goto(BASE + "/medications")
            card = pg.locator(".card-soft", has_text=COURSE).first

            restock = card.get_by_role("button", name="Пополнить")
            await restock.wait_for()
            x, y = await centre(restock)
            await tap(cdp, x, y, drift=6)
            try:
                await pg.get_by_text(TITLE, exact=True).first.wait_for(state="visible", timeout=3000)
                opened = True
            except Exception:
                opened = False
            check("a 6 px drift on «Пополнить» still opens its dialog", opened)
            cancel = pg.locator(".adm-dialog").get_by_text("Отмена", exact=True)
            if await cancel.count():
                await cancel.first.click(timeout=3000)
                await pg.wait_for_timeout(400)

            give = card.get_by_role("button", name=re.compile("Дали сейчас"))
            x, y = await centre(give)
            await tap(cdp, x, y, drift=6)
            await pg.wait_for_timeout(1500)
            still = await card.get_by_role("button", name=re.compile("Дали сейчас")).count()
            check("a 6 px drift on «Дали сейчас» still takes the dose", still == 0)

            # A real swipe, 30 px across the card's padding (no button under the finger): the course must not open.
            await pg.goto(BASE + "/medications")
            box = await pg.locator(".card-soft", has_text=COURSE).first.bounding_box()
            await tap(cdp, box["x"] + 14, box["y"] + 8, drift=-30)
            await pg.wait_for_timeout(800)
            check("a real 30 px swipe across the row does not open the course", "/edit" not in pg.url, pg.url)
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
            await browser.close()
    summary("taps inside swipeable rows")


asyncio.run(main())
