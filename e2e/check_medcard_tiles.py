"""The summary's eight tiles in a grid with no orphan, and the clinic and the food and living conditions as two screens."""

import asyncio
import re

from common import BASE, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        card = f"/pets/{rex}/medical-card"
        await pg.goto(BASE + card + "?mode=fill")
        await pg.wait_for_timeout(2000)
        tiles = await pg.locator(".medsum__tile").evaluate_all("els => els.map(e => e.getAttribute('aria-label'))")
        check("eight tiles", len(tiles) == 8, str(len(tiles)))
        rows = await pg.evaluate(
            "[...new Set([...document.querySelectorAll('.medsum__tile')].map(t => Math.round(t.getBoundingClientRect().top + scrollY)))].length"
        )
        check("they fill four rows of two (no orphan)", rows == 4, str(rows))
        for title, key, want in (
            ("Клиника и врачи", "clinic", ["Ортовет", "Каримов"]),
            ("Питание и условия", "life", ["Сухой корм"]),
        ):
            await pg.goto(BASE + card + "?mode=fill")
            await pg.wait_for_timeout(1200)
            await pg.locator(".medsum__tile").filter(has_text=re.compile("^" + re.escape(title))).click()
            await pg.wait_for_timeout(1500)
            t = await pg.inner_text("body")
            check(
                f"«{title}» opens /{key} with its content",
                pg.url.endswith("/" + key) and title in t and all(x in t for x in want),
                str([x for x in want if x not in t]),
            )
            check(
                f"«{title}»: it does not carry the other part",
                ("Питание и условия" not in t.replace(title, "")) if key == "clinic" else ("Ортовет" not in t),
            )
        await pg.screenshot(path="split_life.png")
        await pg.goto(BASE + card + "?mode=fill")
        await pg.wait_for_timeout(1500)
        await pg.evaluate("window.scrollTo(0, 420)")
        await pg.wait_for_timeout(400)
        await pg.screenshot(path="split_tiles.png")
        check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        await b.close()
    summary("split tiles")


asyncio.run(main())
