"""A «Пополнить» link to a course of another pet opens that course's dialog and chooses its pet.

The dose card links here with the course in the address. The list shows only the chosen pet's courses, so before this a
course of another pet did nothing, and the address kept its mark. A link to a course that does not exist says so.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

COURSE = "Тест-Ссылка"
TITLE = "Пополнить остаток"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(browser, sw=False)
        await login(pg)  # the demo pet «Рекс» is chosen
        made = await api(pg, "POST", "/pets", {"name": "Тест-М", "species": "dog", "gender": "male"})
        pid = ((made["json"] or {}).get("pet") or {}).get("_id")
        try:
            course = (
                await api(
                    pg,
                    "POST",
                    "/medications",
                    {
                        "pet_id": pid,
                        "name": COURSE,
                        "type": "Таблетка",
                        "default_dose": 1,
                        "dose_unit": "таб",
                        "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["23:58"]},
                        "inventory_enabled": True,
                        "inventory_current": 2,
                        "is_active": True,
                    },
                )
            )["json"]["id"]

            await pg.goto(BASE + f"/medications?restock={course}")
            try:
                await pg.get_by_text(TITLE, exact=True).first.wait_for(state="visible", timeout=5000)
                opened = True
            except Exception:
                opened = False
            check("a restock link to another pet's course opens its dialog", opened)
            chosen = await pg.evaluate("() => localStorage.getItem('selectedPetId')")
            check("the course's pet is chosen", pid is not None and pid in (chosen or ""), str(chosen)[:30])
            cancel = pg.locator(".adm-dialog").get_by_text("Отмена", exact=True)
            if await cancel.count():
                await cancel.first.click(timeout=3000)
                await pg.wait_for_timeout(400)

            await pg.goto(BASE + "/medications?restock=" + "0" * 24)
            await pg.wait_for_timeout(2000)
            check("a link to a course that does not exist leaves the address clean", "restock=" not in pg.url, pg.url)
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
            await browser.close()
    summary("restock link")


asyncio.run(main())
