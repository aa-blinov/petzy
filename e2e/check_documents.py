"""Documents as an archive: a file says which record holds it, opens that record, and is found by what the record says.

Needs the local stack and the demo data (docker compose -p petzy-local ... up, scripts/seed_demo.py)."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary


async def titles(pg):
    return [t.strip() for t in await pg.locator("h3").all_inner_texts()]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        await pg.goto(BASE + "/documents")
        await pg.wait_for_timeout(2000)
        sources = await pg.locator(".docs__source").all_inner_texts()
        check(
            "a document held by a record says «Из записи» with its title and day",
            any("Плановый осмотр, 23.09.2026" in s for s in sources),
            str(sources),
        )
        check(
            "a document held by no record says nothing of the kind",
            "Страховка на год" in await titles(pg) and len(sources) < len(await titles(pg)),
        )
        search = pg.locator(".adm-search-bar input")
        await search.fill("плановый осмотр")
        await pg.wait_for_timeout(400)
        check(
            "it is found by the reason of the visit that holds it",
            await titles(pg) == ["Анализ крови"],
            str(await titles(pg)),
        )
        await search.fill("ортовет")
        await pg.wait_for_timeout(400)
        check(
            "it is found by the clinic of the record",
            "Анализ крови" in await titles(pg) and "Страховка на год" not in await titles(pg),
            str(await titles(pg)),
        )
        await search.fill("анализ ортовет")
        await pg.wait_for_timeout(400)
        check("several words must all be there", await titles(pg) == ["Анализ крови"], str(await titles(pg)))
        await search.fill("23.09.2026")
        await pg.wait_for_timeout(400)
        check("it is found by the day of the record", await titles(pg) == ["Анализ крови"], str(await titles(pg)))
        await search.fill("")
        await pg.wait_for_timeout(300)
        await pg.locator(".docs__source", has_text="Плановый осмотр").click()
        await pg.wait_for_timeout(1500)
        check("the line opens the record", "/medical-records/" in pg.url, pg.url.replace(BASE, ""))
        check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        await b.close()
    summary("documents as an archive")


asyncio.run(main())
