"""A flick near the left edge goes back only when it is a back gesture.

The edge swipe (hooks/useSwipeBack) used to listen to the whole document: a sideways
flick that began on a swipeable row, in a field or in a block that scrolls sideways, close
to the left edge, went back a screen nobody asked to leave. It also fired for a slanted
drag. Now it goes back for a quick, clearly horizontal flick from the edge on plain page,
and for nothing else.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402


async def flick(cdp, pg, x, y, dx, dy):
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for i in range(1, 6):
        await cdp.send(
            "Input.dispatchTouchEvent",
            {"type": "touchMove", "touchPoints": [{"x": x + dx * i / 5, "y": y + dy * i / 5}]},
        )
        await pg.wait_for_timeout(15)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await pg.wait_for_timeout(500)


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx, pg = await new_page(browser)
        await login(pg, "demo", "Рекс")
        cdp = await ctx.new_cdp_session(pg)

        async def fresh():
            """Home, then a second screen in the app, so there is a screen to go back to."""
            await pg.goto(BASE + "/")
            await pg.wait_for_selector(".bottom-tab-bar-container", timeout=20000)
            await pg.wait_for_timeout(800)
            await pg.get_by_text("Лекарства", exact=True).last.click()
            await pg.wait_for_url("**/medications", timeout=10000)
            await pg.wait_for_timeout(800)
            # navigate(-1) fires popstate; a tap that opens a screen does not.
            await pg.evaluate(
                "() => { window.__back = 0; window.addEventListener('popstate', () => { window.__back++; }); }"
            )

        async def went_back():
            return await pg.evaluate("window.__back") > 0

        # A plain flick from the edge on empty page goes back.
        await fresh()
        y = await pg.evaluate(
            "() => { for (let y = 60; y < 560; y += 10) { const el = document.elementFromPoint(8, y);"
            " if (el && !el.closest('.swipeable-row, a, button, [role=button]')) return y; } return 60; }"
        )
        await flick(cdp, pg, 8, y, 140, 0)
        check("быстрый свайп от края назад: возвращает на прошлый экран", await went_back(), pg.url)

        # A slanted drag is a scroll, not a back gesture.
        await fresh()
        await flick(cdp, pg, 8, 250, 100, 90)
        check("косой свайп от края: остаёмся", not await went_back(), pg.url)

        # A flick that begins in a field belongs to the field.
        await fresh()
        await pg.evaluate(
            "() => { const i = document.createElement('input'); i.style.cssText = 'position:fixed;left:0;top:300px;width:200px;height:50px;z-index:9999'; document.body.appendChild(i); }"
        )
        await flick(cdp, pg, 8, 320, 140, 0)
        check("свайп, начатый в поле ввода: остаёмся", not await went_back(), pg.url)

        # A flick on a block that scrolls sideways belongs to that block.
        await fresh()
        await pg.evaluate(
            "() => { const d = document.createElement('div'); d.style.cssText = 'position:fixed;left:0;top:300px;width:300px;height:60px;overflow-x:auto;z-index:9999'; d.innerHTML = '<div style=\"width:900px;height:40px\"></div>'; document.body.appendChild(d); }"
        )
        await flick(cdp, pg, 8, 320, 140, 0)
        check("свайп по блоку с горизонтальной прокруткой: остаёмся", not await went_back(), pg.url)

        # A flick on a swipeable row belongs to the row.
        await fresh()
        rows = await pg.locator(".swipeable-row").count()
        if rows:
            box = await pg.locator(".swipeable-row").first.bounding_box()
            await flick(cdp, pg, 8, box["y"] + box["height"] / 2, 140, 0)
            check("свайп, начатый на карточке со свайпом: остаёмся", not await went_back(), pg.url)
        else:
            check("на экране лекарств есть карточка со свайпом", False, "нет .swipeable-row")

        await ctx.close()
        await browser.close()
    summary("the edge swipe goes back only when it is a back gesture")


asyncio.run(main())
