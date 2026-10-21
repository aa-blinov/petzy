"""Three things the UI audit found and that must not come back.

The overdue link on the card is a 44px line to touch, not a 22px one. The empty consent box on
registration is drawn in the secondary text colour, not in the hairline that vanished on cream.
And a page that cannot reach the server while the device is offline says so, instead of blaming
the server. The check signs in as the demo owner and touches nothing else.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary, settle


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        pid = await login(pg)
        await pg.goto(BASE + f"/pets/{pid}/medical-card")
        await settle(pg)
        # The card is one document: no round plus of its own, and each block has its own in its head.
        check("the card has no round plus of its own", await pg.locator(".app-fab").count() == 0)
        for part in ("meds", "prevention", "weight", "visits", "documents", "clinic", "life"):
            await pg.goto(BASE + f"/pets/{pid}/medical-card/{part}")
            await settle(pg)
            check(
                f"«{part}» has its own round plus in its head",
                await pg.locator(f"#medcard-{part} .medcard__add").count() == 1,
            )
        await pg.goto(BASE + f"/pets/{pid}/medical-card")
        await settle(pg)
        link = pg.locator(".medcard__attention-link").first
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
        await settle(pg)
        border = await pg.evaluate(
            "(() => { const e = document.querySelector('.adm-checkbox-icon'); return e ? getComputedStyle(e).borderTopColor : ''; })()"
        )
        check("the empty consent box is drawn in the secondary text colour", border == "rgb(106, 98, 88)", border)
        top = await pg.evaluate(
            "(() => { const box = document.querySelector('div[style*=\"max-width: 400px\"]'); return box ? Math.round(box.getBoundingClientRect().top) : -1; })()"
        )
        check("the register wordmark keeps its 16px gutter from the top edge", top >= 16, str(top))
        await ctx.close()

        ctx, pg = await new_page(browser)
        await login(pg)
        await ctx.set_offline(True)
        await pg.goto(BASE + "/medications", wait_until="commit")
        await pg.get_by_text("Нет связи с интернетом").first.wait_for(timeout=8000)
        check(
            "offline, the page says there is no connection rather than a server fault",
            await pg.get_by_text("Нет связи с интернетом").count() >= 1
            and await pg.get_by_text("Не удалось связаться с сервером").count() == 0,
        )
        await ctx.close()
        await browser.close()
    summary("visual round")


asyncio.run(main())
