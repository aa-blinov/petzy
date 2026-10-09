"""The summary's quick doors: «Записать» beside the weight and «Изменить» beside the allergies open the form or the edit in one tap,
and they are buttons of their own, not inside the tile."""

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
        nested = await pg.locator(".medsum__tile .medsum__quick").count()
        check("the quick door is not inside the tile", nested == 0, f"{nested} nested")
        weight_quick = (
            pg.locator(".medsum__item").filter(has_text="Вес").get_by_role("button", name="Записать", exact=True)
        )
        check("the weight tile has «Записать» beside it", await weight_quick.count() == 1)
        await weight_quick.click()
        await pg.wait_for_url(lambda u: "/form/weight" in u, timeout=15000)
        check("«Записать» opens the weight form in one tap", "/form/weight" in pg.url)
        await pg.goto(BASE + card)
        await pg.locator(".medsum__tile").first.wait_for(timeout=15000)
        await pg.wait_for_timeout(500)
        allergy_quick = (
            pg.locator(".medsum__item").filter(has_text="Здоровье").get_by_role("button", name="Изменить", exact=True)
        )
        check("the health tile has «Изменить» beside it", await allergy_quick.count() == 1)
        await allergy_quick.click()
        await pg.wait_for_url(lambda u: "section=allergies" in u, timeout=15000)
        check("«Изменить» opens the allergies in the profile in one tap", "section=allergies" in pg.url)
        await b.close()
    summary("medcard quick doors")


asyncio.run(main())
