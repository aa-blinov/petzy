"""A long pet name keeps every form on the phone's width.

A name is one line (up to 100 characters), and a single long word in it has no space to break
at: inside the sentence «Питомец: …» on a form it used to push the whole page to 584 px on a
390 px phone, so the page was scaled out and the buttons moved under the fields. Each form that
shows the name in its text must still fit the screen.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle

SCRATCH_PET = "Тест-М-2"
LONG_NAME = "QA очень длинное имя " + "я" * 70

FORMS = ("/form/weight", "/medications/new")


async def make_pet(pg):
    await pg.goto(BASE + "/pets/new")
    await settle(pg)
    await pg.get_by_role("button", name="Собака").click()
    await pg.get_by_placeholder("Имя питомца").fill(LONG_NAME)
    await pg.get_by_role("button", name="Добавить", exact=True).click()
    await settle(pg, 150)
    if await pg.get_by_role("button", name="Закрыть").last.count():
        await pg.get_by_role("button", name="Закрыть").last.click()
    await settle(pg, 150)
    pets = (await api(pg, "GET", "/pets"))["json"]["pets"]
    return next(q["_id"] for q in pets if q["name"] == LONG_NAME)


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
                [pid, LONG_NAME],
            )
            for path in FORMS:
                await pg.goto(BASE + path)
                await settle(pg)
                wide = await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                check(
                    f"{path} with a long pet name fits the phone's width", wide <= 1, f"{wide} px wider than the screen"
                )
        finally:
            if pid:
                await api(pg, "DELETE", f"/pets/{pid}")
        await ctx.close()
        await browser.close()
    summary("a long pet name keeps every form on the phone's width")


asyncio.run(main())
