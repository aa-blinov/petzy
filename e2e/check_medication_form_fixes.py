"""The course form at 320px and for a screen reader, and its small promises.

V-02: the end-date hint uses the whole row and «Убрать» is a button of the row of choices, not laid over the date.
P-23: the whole row «Включить» of «Учёт остатков» toggles, not only the small switch. P-25: the weekday chips are a
group named «Дни недели» and each day has its full name. B-19: «Отменить» after «Завершить курс» brings back the
end date that was planned. P-01: an impossible date typed into «Окончание» refuses the save.

Needs the local stack and the demo data. Makes a scratch pet with a course of its own and removes them.
"""

import asyncio
from datetime import datetime, timedelta

from common import BASE, api, async_playwright, check, login, new_page, settle, summary, wait_until
from scratch import drop_pet, make_pet


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        _ctx, pg = await new_page(b, width=320, height=720, sw=False)
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await login(pg, "demo", "Рекс")
        pid = await make_pet(pg)
        try:
            today = datetime.now().astimezone().date()
            planned = (today + timedelta(days=30)).isoformat()
            course = {
                "pet_id": pid,
                "name": "Т-форма курса",
                "type": "Таблетка",
                "default_dose": 1,
                "dose_unit": "таб",
                "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["09:00"]},
                "is_active": True,
                "started_on": (today - timedelta(days=5)).isoformat(),
                "ended_on": planned,
            }
            made = await api(pg, "POST", "/medications", course)
            mid = made["json"]["id"]
            url = f"{BASE}/medications/{mid}/edit"

            async def stored():
                return (await api(pg, "GET", f"/medications/{mid}"))["json"]["medication"]

            await pg.goto(url)
            await wait_until(pg, lambda t: "Окончание" in t)
            await settle(pg)

            # V-02: the hint is not squeezed, and «Убрать» is not over the date
            hint = pg.get_by_text("Последний день курса").first
            box = await hint.bounding_box()
            check(
                "the end-date hint spans the row, not a column of letters",
                box is not None and box["width"] > 180,
                str(box),
            )
            check("its line count is small", box is not None and box["height"] < 90, str(box))
            check("«Убрать» is not laid over the date", await pg.locator(".datefield__clear").count() == 0)
            clear = pg.get_by_role("button", name="Убрать дату окончания")
            check("it is a button of the row of choices", await clear.count() == 1)
            overflow = await pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            check("and the page does not slide sideways", not overflow)

            # P-25: the weekday chips have a name
            check(
                "the weekdays are a group named «Дни недели»",
                await pg.get_by_role("listbox", name="Дни недели").count() == 1,
            )
            check(
                "and a day is named in full",
                await pg.get_by_role("option", name="Понедельник").count() == 1
                and await pg.get_by_role("option", name="Воскресенье").count() == 1,
            )

            # P-23: the label toggles the row
            switch = pg.get_by_role("switch", name="Следить за остатком")
            before = await switch.get_attribute("aria-checked")
            await pg.get_by_text("Следить за остатком", exact=True).click()
            await settle(pg, 150)
            after = await switch.get_attribute("aria-checked")
            check("a tap on the label «Следить за остатком» toggles the stock", before != after, f"{before} -> {after}")
            await pg.get_by_text("Следить за остатком", exact=True).click()
            await settle(pg, 150)
            check("and again back", await switch.get_attribute("aria-checked") == before)

            # P-01: an impossible end date is refused
            await pg.get_by_role("button", name="Ввести цифрами", exact=True).nth(1).click()
            await pg.locator('input[aria-label="Окончание, цифрами"]').fill("31022026")
            body = await wait_until(pg, lambda t: "Такой даты нет" in t)
            check("an impossible end date is named", "Такой даты нет" in body)
            await pg.get_by_role("button", name="Сохранить", exact=True).click()
            await settle(pg, 300)
            check("the save is refused, the form stays", "/edit" in pg.url)
            check(
                "and the planned end is kept",
                (await stored())["ended_on"] == planned,
                str((await stored())["ended_on"]),
            )

            # B-19: «Завершить курс» then «Отменить» brings the planned end back
            await pg.goto(url)
            await wait_until(pg, lambda t: "Завершить курс" in t)
            await pg.get_by_role("button", name="Завершить курс").click()
            await pg.wait_for_url(lambda u: "/edit" not in u, timeout=15000)
            ended = await stored()
            check("the course is ended as of today", ended["ended_on"] == today.isoformat(), str(ended["ended_on"]))
            bar = pg.locator(".snackbar")
            await bar.get_by_role("button", name="Отменить").click(timeout=10000)
            await settle(pg, 300)
            back = await stored()
            check(
                "undo brings back the planned end date",
                back["ended_on"] == planned and back["is_active"],
                f"{back['ended_on']} {back['is_active']}",
            )
        finally:
            await drop_pet(pg, pid)
            await b.close()
    return summary("форма курса: 320px, чтение с экрана, отмена")


asyncio.run(main())
