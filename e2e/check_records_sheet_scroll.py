"""The sheet «Все прививки и обработки» fits the screen and scrolls inside: both kinds are reachable, and a finger
that scrolls the list back up from its foot brings it to the top instead of pulling the sheet shut.

The sheet used to have no height of its own: a long list grew past the screen, its foot (the vaccinations, below
the treatments) was cut off, the list never scrolled, and pulling it back up closed the sheet onto the card.

Needs the local stack and the demo data (docker compose -p petzy-local ... up, scripts/seed_demo.py)."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, settle, summary, wait_until

SHEET = ".adm-popup-body [role=dialog]"


async def touch_drag(pg, x: float, y_from: float, y_to: float) -> None:
    """A real finger: the sheet listens to touch pointers, and the list scrolls natively under them."""
    cdp = await pg.context.new_cdp_session(pg)
    steps = 8
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y_from}]})
    for i in range(1, steps + 1):
        y = y_from + (y_to - y_from) * i / steps
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
        await pg.wait_for_timeout(30)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await pg.wait_for_timeout(400)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        # A small phone: the list is taller than the screen here for sure.
        ctx, pg = await new_page(b, width=375, height=667, sw=False)
        rex = await login(pg, "demo", "Рекс")
        await pg.goto(f"{BASE}/pets/{rex}/medical-card")
        await wait_until(pg, lambda t: "Прививки и обработки" in t)
        await settle(pg)

        door = (
            pg.locator("#medcard-prevention, .medcard__section")
            .filter(has_text="Прививки и обработки")
            .get_by_text("Показать все")
        )
        check("the prevention block has the door to the whole list", await door.count() >= 1)
        total = int("".join(ch for ch in await door.first.inner_text() if ch.isdigit()))
        await door.first.click()
        sheet = pg.locator(SHEET).filter(has_text="Все прививки и обработки")
        await sheet.wait_for()
        await pg.wait_for_timeout(600)

        box = await sheet.bounding_box()
        check(
            "the sheet fits the screen",
            box is not None and box["y"] >= 0 and box["y"] + box["height"] <= 667 + 1,
            str(box),
        )
        rows = sheet.locator(".medcard__list--sheet > li")
        check(
            "the list holds every record the door counts, the vaccinations as well as the treatments",
            await rows.count() == total,
            f"{await rows.count()} rows of {total}",
        )

        scroller = sheet.locator(":scope > div").nth(1)
        sizes = await scroller.evaluate("e => [e.scrollHeight, e.clientHeight]")
        check("the list scrolls inside the sheet", sizes[0] > sizes[1], str(sizes))

        sb = await scroller.bounding_box()
        x = sb["x"] + sb["width"] / 2
        # To the foot of the list.
        for _ in range(6):
            await touch_drag(pg, x, sb["y"] + sb["height"] - 40, sb["y"] + 40)
        at_foot = await scroller.evaluate("e => Math.ceil(e.scrollTop + e.clientHeight) >= e.scrollHeight - 2")
        last_visible = await rows.last.is_visible()
        check("the foot of the list is reachable", at_foot and last_visible)

        # And back up: the list scrolls to its top, the sheet stays.
        for _ in range(6):
            await touch_drag(pg, x, sb["y"] + 40, sb["y"] + sb["height"] - 40)
            if await scroller.evaluate("e => e.scrollTop") <= 0:
                break
        check("scrolling back up from the foot keeps the sheet open", await sheet.is_visible())
        check("the list is back at its top", await scroller.evaluate("e => e.scrollTop") <= 0)

        # At the top, pulling further down is the close, as it was.
        await touch_drag(pg, x, sb["y"] + 40, sb["y"] + 300)
        await pg.wait_for_timeout(500)
        check(
            "at the top, a pull down still closes the sheet",
            await pg.locator(SHEET).count() == 0 or not await sheet.is_visible(),
        )

        await ctx.close()
        await b.close()
    summary("records sheet scroll")


asyncio.run(main())
