"""A create whose answer got lost must not leave two of them when the person presses the button again.

The request reaches the server and is written, the browser is told the connection broke: exactly the moment a person
answers «Сервер не ответил» by pressing again. The forms send an `Idempotency-Key`, so the repeat is answered with the
first answer. A changed field after the failure is a different request and is stored.

Needs the local stand and the demo data. Makes a scratch pet «Тест-М» of its own and removes it.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, settle, summary
from scratch import drop_pet, make_pet


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        pid = await make_pet(pg)
        try:
            lost = {"on": True}

            async def lose_the_answer(route):
                if lost["on"] and route.request.method == "POST":
                    await route.fetch()
                    await route.abort("failed")
                else:
                    await route.continue_()

            await pg.route("**/api/medical-records", lose_the_answer)
            await pg.goto(f"{BASE}/pets/{pid}/medical-records/new?kind=vaccination")
            await settle(pg)
            await pg.get_by_text("Название вакцины").first.click()
            await pg.wait_for_function(
                "() => document.activeElement && document.activeElement.tagName === 'INPUT'", timeout=8000
            )
            await pg.keyboard.type("Своя вакцина")
            await pg.locator(".prodpick__row--own").wait_for(timeout=8000)
            await pg.locator(".prodpick__row--own").click()
            await pg.locator(".prodpick__row--own").wait_for(state="hidden", timeout=8000)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await settle(pg, 150)

            def vaccinations(rows):
                return [r for r in rows if r["kind"] == "vaccination"]

            rows = vaccinations((await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"])
            check("the first send is written on the server though its answer was lost", len(rows) == 1, str(len(rows)))
            check("the form is still open and says nothing was confirmed", "/medical-records/new" in pg.url, pg.url)

            lost["on"] = False
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await settle(pg, 300)
            rows = vaccinations((await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"])
            check("pressing again leaves one record, not two", len(rows) == 1, str([r["title"] for r in rows]))
        finally:
            await drop_pet(pg, pid)
            await b.close()
    return summary("повтор после потерянного ответа")


asyncio.run(main())
