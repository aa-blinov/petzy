"""On the feed the chevron sits at the card's right edge, a date stays clear of the round «+», and the «+» is never hidden.

Commit 55a50b3 reserved the right side of every card for the «+», which moved the chevron and the date in from the edge.
The date now ends just left of the round button's column: the chevron keeps the edge, the date is never under the button.
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
        chevron_gaps, date_gaps, date_tops = [], [], []
        for i in range(min(await cards.count(), 4)):
            card = cards.nth(i)
            box = await card.bounding_box()
            chevron = await card.locator("svg.lucide-chevron-right").bounding_box()
            chevron_gaps.append(round(box["x"] + box["width"] - (chevron["x"] + chevron["width"]), 1))
            date = await card.locator(".feed-date").first.bounding_box()
            if date:
                date_gaps.append(round(box["x"] + box["width"] - (date["x"] + date["width"]), 1))
                date_tops.append(round(date["y"] - box["y"], 1))
        check(
            "each feed card's chevron sits at its own right edge",
            bool(chevron_gaps) and max(chevron_gaps) <= 24,
            f"gaps {chevron_gaps}",
        )
        check(
            "each feed card's date sits at its top right, just left of the round +",
            bool(date_gaps) and all(70 <= g <= 100 for g in date_gaps) and all(t <= 30 for t in date_tops),
            f"right gaps {date_gaps}, tops {date_tops}",
        )
        overlaps = []
        for y in range(0, 3200, 40):
            await pg.evaluate(f"window.scrollTo(0, {y})")
            await pg.wait_for_timeout(60)
            overlaps.append(
                await pg.evaluate("""() => {
                const fab = document.querySelector('.app-fab');
                if (!fab) return 0;
                const f = fab.getBoundingClientRect();
                return [...document.querySelectorAll('.feed-date')].filter((el) => {
                    const b = el.getBoundingClientRect();
                    return b.bottom > f.top && b.top < f.bottom && b.right > f.left && b.left < f.right;
                }).length;
            }""")
            )
        check(
            "the round + never covers a feed date",
            sum(overlaps) == 0,
            f"{sum(1 for n in overlaps if n)} of {len(overlaps)} scroll steps with a date under it",
        )
        await browser.close()
    summary("feed chevron and date")


asyncio.run(main())
