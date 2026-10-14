"""Three things the UI audit found and that must not come back.

The overdue link on the card is a 44px line to touch, not a 22px one. The empty consent box on
registration is drawn in the secondary text colour, not in the hairline that vanished on cream.
And a page that cannot reach the server while the device is offline says so, instead of blaming
the server. The check signs in as the demo owner and touches nothing else.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        pid = await login(pg)
        await pg.goto(BASE + f"/pets/{pid}/medical-card?mode=fill")
        await pg.wait_for_timeout(1800)
        # The round plus is put aside at the top of the card: its last row of tiles is where it would stand.
        check(
            "the round plus stays aside at the top of the card",
            await pg.locator(".app-fab--away").count() == 1,
        )
        await pg.evaluate("window.scrollBy(0, 700)")
        await pg.wait_for_timeout(400)
        # The card is shorter than 700px of scroll: this lands mid-page, off the top zone where it stays aside.
        await pg.evaluate("window.scrollBy(0, -200)")
        await pg.wait_for_timeout(600)
        check(
            "and it comes back on a scroll up",
            await pg.locator(".app-fab:not(.app-fab--away)").count() == 1,
        )
        await pg.evaluate("window.scrollTo(0, 0)")
        await pg.wait_for_timeout(600)
        link = pg.locator(".medcard__alert-link").first
        if await link.count():
            box = await link.bounding_box()
            check(
                "the overdue link is at least 44px high",
                box is not None and box["height"] >= 44,
                str(box and box["height"]),
            )
        else:
            check("the overdue link is at least 44px high (no overdue item on the demo pet)", True, "skipped")
        await ctx.close()

        ctx, pg = await new_page(browser)
        await pg.goto(BASE + "/register")
        await pg.wait_for_timeout(1800)
        border = await pg.evaluate(
            "(() => { const e = document.querySelector('.adm-checkbox-icon'); return e ? getComputedStyle(e).borderTopColor : ''; })()"
        )
        check("the empty consent box is drawn in the secondary text colour", border == "rgb(106, 98, 88)", border)
        await ctx.close()

        ctx, pg = await new_page(browser)
        await login(pg)
        await ctx.set_offline(True)
        await pg.goto(BASE + "/history", wait_until="commit")
        await pg.wait_for_timeout(2500)
        check(
            "offline, the page says there is no connection rather than a server fault",
            await pg.get_by_text("Нет связи с интернетом").count() >= 1
            and await pg.get_by_text("Не удалось связаться с сервером").count() == 0,
        )
        await ctx.close()
        await browser.close()
    summary("visual round")


asyncio.run(main())
