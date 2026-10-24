"""The record form's choices and exits, and the round «+» that logs a one-off event.

P-07: «Записать повторную прививку» then «Добавить» ends on the medical card, never back on the record it repeats.
P-06: «Вес в этот день» of a visit shows the weight of that day (the last one) and opens the weight history.
P-09: the clinic and the doctor can be «Другая…» / «Другой…», typed in the row; a doctor does not change a chosen clinic.
P-13: «Другие записи» in the «+» sheet lists the other event types, and a tap on one opens its form.

Needs the local stack and the demo data. Makes a scratch pet of its own and removes it.
"""

import asyncio
from datetime import datetime, timedelta

from common import BASE, api, async_playwright, check, login, new_page, settle, summary, swipe_wheel, wait_until
from scratch import NAME, drop_pet, make_pet, make_record

PROFILE = {
    "clinics": [
        {"name": "Айболит", "doctors": [{"name": "Иванова И.И."}]},
        {"name": "Лапка", "doctors": [{"name": "Петров П.П."}]},
    ]
}


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await login(pg, "demo", "Рекс")
        pid = await make_pet(pg, PROFILE)
        try:
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, NAME],
            )
            today = datetime.now().astimezone().date()
            day = (today - timedelta(days=3)).isoformat()

            # P-07: the repeat ends on the card
            rid = await make_record(
                pg, pid, "vaccination", "Нобивак", day, next_due=(today + timedelta(days=200)).isoformat()
            )
            card = f"/pets/{pid}/medical-card"
            await pg.goto(f"{BASE}/pets/{pid}/medical-records/{rid}")
            await wait_until(pg, lambda t: "Записать повторную прививку" in t)
            await pg.get_by_role("button", name="Записать повторную прививку").click()
            await wait_until(pg, lambda t: "Повторная прививка" in t)
            check("the repeat form opened", "/medical-records/new" in pg.url and "from=" in pg.url, pg.url)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.wait_for_url(lambda u: u.rstrip("/").endswith("/medical-card"), timeout=15000)
            await settle(pg, 200)
            check("a saved repeat ends on the medical card", pg.url.endswith(card), pg.url)
            records = [
                r
                for r in (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
                if r["kind"] == "vaccination"
            ]
            check("and it is a new record beside the old one", len(records) == 2, str(len(records)))

            # P-06: the visit's weight row
            visit_day = (today - timedelta(days=2)).isoformat()
            for time_, kilos in (("08:00", 4.65), ("09:00", 6.6)):
                await api(
                    pg,
                    "POST",
                    "/events",
                    {
                        "pet_id": pid,
                        "type": "weight",
                        "date": visit_day,
                        "time": time_,
                        "fields": {"weight": kilos},
                        "tz": "Europe/Moscow",
                    },
                )
            vid = await make_record(pg, pid, "visit", "Осмотр", visit_day)
            await pg.goto(f"{BASE}/pets/{pid}/medical-records/{vid}")
            row = pg.get_by_text("Вес в этот день")
            await row.wait_for(timeout=15000)
            text = await pg.inner_text("body")
            check(
                "the visit's weight row shows the last weight of the day",
                "6,6 кг" in text and "4,65" not in text,
                text[-400:].replace("\n", " | "),
            )
            await row.click()
            await pg.wait_for_url(lambda u: u.rstrip("/").endswith("/medical-card/weight"), timeout=15000)
            check(
                "and opens the weight history, not an empty form",
                "/medical-card/weight" in pg.url and "/form/" not in pg.url,
                pg.url,
            )

            # P-09: «Другая…» clinic, «Другой…» doctor
            await pg.goto(f"{BASE}/pets/{pid}/medical-records/new?kind=vaccination")
            await settle(pg)
            await pg.get_by_text("Серия, клиника, врач и заметка").click()
            await settle(pg)
            await pg.get_by_text("Врач", exact=True).click()
            await settle(pg, 150)
            items = await pg.locator(".adm-picker-view-column-item").all_inner_texts()
            check("the doctor wheel ends with «Другой…»", items and items[-1] == "Другой…", str(items))
            await swipe_wheel(pg, ctx, 0, 2)
            await pg.get_by_role("button", name="Готово").last.click()
            await settle(pg, 150)
            body = await pg.inner_text("body")
            check(
                "a doctor chosen without a clinic puts his clinic, and says so",
                "Лапка" in body and "поставлена по врачу" in body,
                body[-300:].replace("\n", " | "),
            )
            # The closed doctor wheel stays in the page, hidden: the clinic wheel is the only one left to turn.
            await pg.evaluate(
                "() => document.querySelectorAll('.adm-popup').forEach(p => { if (getComputedStyle(p).display === 'none') p.remove(); })"
            )
            await pg.get_by_text("Клиника", exact=True).click()
            await settle(pg, 150)
            items = await pg.locator(".adm-picker-view-column-item").all_inner_texts()
            check("the clinic wheel ends with «Другая…»", items and items[-1] == "Другая…", str(items))
            await swipe_wheel(pg, ctx, 0, len(items) - 1 - items.index("Лапка"), up=True)
            await pg.get_by_role("button", name="Готово").last.click()
            await settle(pg, 150)
            field = pg.get_by_placeholder("Название клиники")
            check("«Другая…» turns the row into a text field", await field.count() == 1)
            await field.fill("Вет-Дом")
            await settle(pg, 150)
            check("a one-off clinic is typed in, with no detour to the profile", await field.input_value() == "Вет-Дом")

            # P-13: the «+» sheet lists the other event types
            await pg.goto(BASE + "/")
            await settle(pg)
            await pg.locator(".app-fab").click()
            sheet = pg.locator(".adm-popup").filter(has_text="Что записать?")
            await sheet.get_by_text("Другие записи").first.wait_for(state="visible", timeout=10000)
            before = await sheet.locator("button").count()
            await sheet.get_by_role("button", name="Другие записи").click()
            await settle(pg, 150)
            after = await sheet.locator("button").count()
            check("«Другие записи» lists more types in the sheet", after > before, f"{before} -> {after}")
            check("and does not leave for the settings", "/pet-events" not in pg.url, pg.url)
            tile = (
                sheet.locator("button").filter(has_not_text="Настроить").nth(before - 1)
            )  # the first of the added types
            await tile.click()
            await settle(pg, 200)
            check("a tap on one of them opens its form", "/form/" in pg.url, pg.url)
        finally:
            await drop_pet(pg, pid)
            await b.close()
    return summary("форма записи: выборы, выходы, «Другие записи»")


asyncio.run(main())
