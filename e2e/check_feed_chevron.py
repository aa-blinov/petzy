"""The chevron of a feed card sits at the card's own right edge, and the feed's text keeps clear of the round «+».

Commit 55a50b3 moved the clearance for the «+» onto the whole card, which pushed every chevron 64 px in from the edge.
The clearance now belongs to the text alone.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(browser, sw=False)
        await login(pg)
        await pg.goto(BASE + "/")
        cards = pg.locator(".card-soft--interactive", has=pg.locator("svg.lucide-chevron-right"))
        await cards.first.wait_for(timeout=15000)
        gaps, clear = [], []
        for i in range(min(await cards.count(), 4)):
            card = cards.nth(i)
            box = await card.bounding_box()
            chevron = await card.locator("svg.lucide-chevron-right").bounding_box()
            gaps.append(round(box["x"] + box["width"] - (chevron["x"] + chevron["width"]), 1))
            details = await card.locator(".clamp-3").first.bounding_box()
            if details:
                clear.append(round(box["x"] + box["width"] - (details["x"] + details["width"]), 1))
        check("each feed card's chevron sits at its own right edge", bool(gaps) and max(gaps) <= 24, f"gaps {gaps}")
        check("the feed's text keeps clear of the round «+»", bool(clear) and min(clear) >= 56, f"clear {clear}")
        await browser.close()
    summary("feed chevron")


asyncio.run(main())
