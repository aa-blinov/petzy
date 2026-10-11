"""The card's tiles only open their parts: no action sits on a tile or in the overdue strip. The actions live in the sections.

Needs the local stack and the demo data (docker compose -p petzy-local ... up, scripts/seed_demo.py)."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        card = f"/pets/{rex}/medical-card"
        await pg.goto(BASE + card)
        await pg.locator(".medsum__tile").first.wait_for(timeout=15000)
        await pg.wait_for_timeout(500)
        check("no tile carries a second button", await pg.locator(".medsum__item button").count() == 0)
        check(
            "no «Записать» or «Изменить» button on the card",
            await pg.get_by_role("button", name="Записать", exact=True).count() == 0
            and await pg.get_by_role("button", name="Изменить", exact=True).count() == 0,
        )
        check(
            "the overdue strip is text: no button, and it says where the repeat is written",
            await pg.locator(".medcard__alert button").count() == 0
            and "Профилактика" in await pg.locator(".medcard__alert").inner_text(),
        )
        await pg.get_by_role("button", name="Вес: 29,3 кг, 04.10.2026").click()
        await pg.wait_for_timeout(800)
        check(
            "the weight is recorded inside its section",
            await pg.get_by_role("button", name="Записать вес", exact=True).count() == 1,
        )
        await pg.goto(BASE + card + "/risks")
        await pg.wait_for_timeout(800)
        check(
            "the allergies are changed inside their section",
            await pg.get_by_role("button", name="Изменить", exact=True).count() >= 1,
        )
        await b.close()
    summary("medcard actions in the sections")


asyncio.run(main())
