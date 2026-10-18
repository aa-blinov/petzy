"""A record that is gone says so: «Такой записи нет», and no «Повторить».

Opening the address of a record that was deleted (an old link, a second tab) used to say that
the record did not load and offer to try again: a retry cannot bring back a record that is not
there. A record that cannot be reached for another reason keeps its «Повторить».
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle

SCRATCH_PET = "Тест-К"


async def make_pet(pg):
    await pg.goto(BASE + "/pets/new")
    await settle(pg)
    await pg.get_by_role("button", name="Собака").click()
    await pg.get_by_placeholder("Имя питомца").fill(SCRATCH_PET)
    await pg.get_by_role("button", name="Добавить", exact=True).click()
    await settle(pg, 150)
    if await pg.get_by_role("button", name="Готово").count():
        await pg.get_by_role("button", name="Готово").click()
    await settle(pg, 150)
    pets = (await api(pg, "GET", "/pets"))["json"]["pets"]
    return next(q["_id"] for q in pets if q["name"] == SCRATCH_PET)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx, pg = await new_page(browser, width=390, height=844)
        await login(pg, "demo", "Рекс")
        pid = None
        try:
            pid = await make_pet(pg)
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, SCRATCH_PET],
            )
            await pg.goto(BASE + "/form/weight")
            await settle(pg)
            await pg.get_by_label("Вес (кг)").fill("10,5")
            await pg.get_by_role("button", name="Создать").click()
            await settle(pg, 150)
            items = (await api(pg, "GET", f"/events?pet_id={pid}&type=weight"))["json"]["items"]
            rid = items[0]["_id"] if items else None
            check("a weight record was made to delete", rid is not None)
            if rid:
                await api(pg, "DELETE", f"/events/{rid}")
                await pg.goto(BASE + f"/form/weight/{rid}")
                await settle(pg)
                text = await pg.inner_text("body")
                check(
                    "the form of a record that is gone says so",
                    "Такой записи нет" in text,
                    text[:120].replace(chr(10), " | "),
                )
                check(
                    "and offers no retry for it",
                    "Повторить" not in text and "Запись не загрузилась" not in text,
                )
        finally:
            if pid:
                await api(pg, "DELETE", f"/pets/{pid}")
        await ctx.close()
        await browser.close()
    summary("a record that is gone says so")


asyncio.run(main())
