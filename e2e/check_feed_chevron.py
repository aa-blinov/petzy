"""On the feed the chevron sits at the card's right edge, and the date sits at the top right, in line with it.

The round «+» may stand over the end of a date while the list is scrolled: that was the trade-off the owner asked for.
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
        chevron_gaps, date_gaps, date_tops, overlaps, edges = [], [], [], [], []
        for i in range(await cards.count()):
            card = cards.nth(i)
            box = await card.bounding_box()
            chevron = await card.locator("svg.lucide-chevron-right").bounding_box()
            chevron_gaps.append(round(box["x"] + box["width"] - (chevron["x"] + chevron["width"]), 1))
            date = await card.locator(".feed-date").first.bounding_box()
            if date:
                edges.append(abs((date["x"] + date["width"]) - (chevron["x"] + chevron["width"])) <= 2)
                date_gaps.append(round(box["x"] + box["width"] - (date["x"] + date["width"]), 1))
                date_tops.append(round(date["y"] - box["y"], 1))
                overlaps.append(
                    date["y"] < chevron["y"] + chevron["height"]
                    and date["y"] + date["height"] > chevron["y"]
                    and date["x"] < chevron["x"] + chevron["width"]
                    and date["x"] + date["width"] > chevron["x"]
                )
        check(
            "each feed card's chevron sits at its own right edge",
            bool(chevron_gaps) and max(chevron_gaps) <= 24,
            f"gaps {chevron_gaps}",
        )
        check(
            "each feed card's date sits at its top right, in line with the chevron",
            bool(date_gaps) and all(12 <= g <= 22 for g in date_gaps) and all(t <= 30 for t in date_tops),
            f"right gaps {date_gaps}, tops {date_tops}",
        )
        check("the date never runs into the chevron", bool(overlaps) and not any(overlaps), f"overlaps {overlaps}")
        check("the date and the chevron share their right edge", bool(edges) and all(edges), f"aligned {edges}")
        await browser.close()
    summary("feed chevron and date")


asyncio.run(main())
