"""The medicine card's quieter actions: «Завершить курс» lives in the «Действия» menu (a 44px kebab on a touch screen) and
is undone from the bar, the extra doses of a day are said on the card, the «Форма выпуска» is a list sheet where a tap
chooses and closes (no «Готово»), and the intake sheet offers the same chips as the feed.

Needs the local stack and the demo data. Makes a course of its own for the demo pet and removes it.
"""

import asyncio
from datetime import datetime

from common import BASE, api, async_playwright, check, login, new_page, settle, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        _ctx, pg = await new_page(b, width=390, height=844, sw=False)
        pid = await login(pg, "demo", "Рекс")
        mid = None
        now = datetime.now()
        if not "10:00" < now.strftime("%H:%M") < "23:50":
            print("SKIP the clock is at a day's edge")
            return
        today = now.strftime("%Y-%m-%d")
        try:
            course = {
                "pet_id": pid,
                "name": "Т-карточка лекарства",
                "type": "Таблетка",
                "default_dose": 1,
                "dose_unit": "таб",
                "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["00:01"]},
                "is_active": True,
            }
            made = await api(pg, "POST", "/medications", course)
            mid = made["json"]["id"]

            async def stored():
                return (await api(pg, "GET", f"/medications/{mid}"))["json"]["medication"]

            await pg.goto(BASE + "/medications")
            await settle(pg)
            card = pg.locator(".card-soft", has_text="Т-карточка лекарства").first
            check(
                "«Завершить курс» is no longer a button on the card",
                await card.get_by_role("button", name="Завершить курс").count() == 0,
            )
            kebab = pg.get_by_role("button", name="Действия: Т-карточка лекарства", exact=True)
            box = await kebab.bounding_box()
            check(
                "the actions button is visible on a touch screen, 44px",
                box is not None and box["width"] >= 44 and box["height"] >= 44,
                str(box),
            )

            # one dose, then three more written by the API (a twin within half an hour is refused, so they are hours apart): the card says so
            await card.get_by_role("button", name="Дали сейчас").click()
            await settle(pg, 300)
            for minute in ("03:00", "06:00", "09:00"):
                await api(pg, "POST", f"/medications/{mid}/log", {"date": today, "time": minute, "tz": "Asia/Almaty"})
            await pg.reload()
            await settle(pg)
            text = await pg.locator(".card-soft", has_text="Т-карточка лекарства").first.inner_text()
            check(
                "extra doses are said on the card",
                "Сегодня 1 из 1, ещё приёмов: 3" in text,
                text.replace("\n", " | ")[:200],
            )

            # the intake sheet: the feed's chips
            await card.get_by_role("button", name="Записать дополнительный приём").click()
            await settle(pg, 200)
            for label in ("Сейчас", "Час назад", "Вчера вечером", "Выбрать время"):
                check(f"the intake sheet offers «{label}»", await pg.get_by_role("button", name=label).count() > 0)
            check("«15 минут назад» is gone", await pg.get_by_role("button", name="15 минут назад").count() == 0)
            await pg.get_by_role("button", name="Отмена", exact=True).click()
            await settle(pg, 300)

            # ending the course from the menu, and the bar takes it back
            await kebab.click()
            await pg.get_by_role("button", name="Завершить курс", exact=True).click()
            await settle(pg, 400)
            check("the course is ended from the menu", (await stored()).get("is_active") is False)
            await pg.get_by_role("button", name="Отменить").first.click()
            await settle(pg, 400)
            check("«Отменить» brings the course back", (await stored()).get("is_active") is True)

            # the form: «Форма выпуска» is a list, a tap chooses and closes
            await pg.goto(f"{BASE}/medications/{mid}/edit")
            await settle(pg)
            await pg.get_by_text("Форма выпуска").first.click()
            await settle(pg, 300)
            check("the list has no «Готово»", await pg.get_by_role("button", name="Готово").count() == 0)
            await pg.get_by_role("option", name="Сироп", exact=True).click()
            await settle(pg, 300)
            check("a tap closes the list", await pg.get_by_role("option", name="Сироп", exact=True).count() == 0)
            check("the chosen form stands in the row", await pg.get_by_text("Сироп").count() > 0)
        finally:
            if mid:
                await api(pg, "DELETE", f"/medications/{mid}")
        await b.close()
    summary("the medicine card actions")


asyncio.run(main())
