"""The medical card's summary and screens: tiles first, the sections, the round «+», a repeat from a record, the weight note.

Needs the local stack and the demo data (docker compose -p petzy-local ... up, scripts/seed_demo.py)."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        card = f"/pets/{rex}/medical-card"
        await pg.goto(BASE + card + "?mode=fill")
        await pg.wait_for_timeout(2000)
        ty = await pg.evaluate("Math.round(document.querySelector('.medsum__tile').getBoundingClientRect().top)")
        vis = await pg.evaluate(
            "[...document.querySelectorAll('.medsum__tile')].filter(t => t.getBoundingClientRect().bottom <= innerHeight - 56).length"
        )
        check("tiles start high on the first screen", ty < 420, f"first tile at y={ty}")
        check("at least four tiles are fully visible without scrolling", vis >= 4, f"{vis} of 8")
        body = await pg.inner_text("body")
        check("the PDF button is not on the summary", "Скачать PDF" not in body and "Показать врачу" not in body)
        order = await pg.evaluate(
            "(() => { const a = document.querySelector('.medsum').getBoundingClientRect().top, b = [...document.querySelectorAll('h2')].find(h => h.textContent.includes('К приёму')).getBoundingClientRect().top; return a < b; })()"
        )
        check("tiles come before «К приёму»", order)
        tiles = await pg.locator(".medsum__tile").evaluate_all("els => els.map(e => e.getAttribute('aria-label'))")
        check("the first tile is «Здоровье и аллергии»", tiles[0].startswith("Здоровье и аллергии"), tiles[0])
        await pg.locator(".medsum__tile").first.click()
        await pg.wait_for_timeout(1500)
        check("its screen has the same title", "Здоровье и аллергии" in (await pg.inner_text("h1")))
        await pg.get_by_role("button", name="Изменить").first.click()
        await pg.wait_for_timeout(1500)
        check("«Изменить» opens the profile at the allergies", "section=allergies" in pg.url, pg.url.replace(BASE, ""))
        # the round plus steps aside on a scroll down and returns on a scroll up
        await pg.goto(BASE + card + "/prevention")
        await pg.wait_for_timeout(1500)
        check("the round plus is there at the top", await pg.locator(".app-fab:not(.app-fab--away)").count() == 1)
        await pg.mouse.wheel(0, 500)
        await pg.wait_for_timeout(500)
        await pg.evaluate("window.scrollBy(0, 300)")
        await pg.wait_for_timeout(500)
        check("it steps aside on a scroll down", await pg.locator(".app-fab--away").count() == 1)
        await pg.evaluate("window.scrollBy(0, -200)")
        await pg.wait_for_timeout(500)
        check("it comes back on a scroll up", await pg.locator(".app-fab--away").count() == 0)
        # repeat from an existing record
        recs = (await api(pg, "GET", f"/medical-records?pet_id={rex}"))["json"]
        items = recs if isinstance(recs, list) else recs.get("items") or recs.get("records") or []
        vac = next(r for r in items if r.get("kind") == "vaccination")
        await pg.goto(BASE + f"/pets/{rex}/medical-records/{vac['_id']}")
        await pg.wait_for_timeout(1800)
        check(
            "an existing vaccination offers «Записать повторную прививку»",
            await pg.get_by_role("button", name="Записать повторную прививку").count() == 1,
        )
        await pg.get_by_role("button", name="Записать повторную прививку").click()
        await pg.wait_for_timeout(1500)
        check("it opens the same-again form", "from=" in pg.url and "Повторная прививка" in await pg.inner_text("h1"))
        # duplicate weight note
        await pg.evaluate("new Date().toISOString().slice(0, 10)")
        await pg.goto(BASE + f"/pets/{rex}/medical-records/new?kind=visit")
        await pg.wait_for_timeout(1800)
        t = await pg.inner_text("body")
        check(
            "a visit today with a weight already today says so under the weight field",
            "уже записан" in t or "Если взвешивали" in t,
            t[t.find("Вес, кг") :][:140].replace(chr(10), " | "),
        )
        check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        await pg.goto(BASE + card + "?mode=fill")
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path="c1_summary.png")
        await b.close()
    summary("first batch")


asyncio.run(main())
