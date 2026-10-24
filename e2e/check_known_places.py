"""The clinic and the doctor wheels of a record offer every clinic and doctor the person has already named.

Not only the last ten records of this pet (the card shows no more), and not only this pet's: a clinic named for another pet of the
same person is offered too.

Needs the local stand and the demo data. Makes two scratch pets of its own and removes them.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, settle, summary
from scratch import drop_pet, make_pet


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        first = await make_pet(pg)
        second = None
        try:
            for i in range(1, 13):
                await api(
                    pg,
                    "POST",
                    "/medical-records",
                    {
                        "pet_id": first,
                        "kind": "vaccination",
                        "title": f"Вакцина {i}",
                        "date": f"2026-01-{i:02d}",
                        "clinic": f"Клиника {i}",
                        "vet": f"Врач {i}",
                    },
                )
            # the same person's other pet, a clinic and a doctor only that one has
            await pg.goto(BASE + "/pets/new")
            await settle(pg)
            await pg.get_by_role("button", name="Кот").click()
            await pg.get_by_placeholder("Имя питомца").fill("Тест-К")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await settle(pg, 150)
            if await pg.get_by_role("button", name="Закрыть").count():
                await pg.get_by_role("button", name="Закрыть").last.click()
            await settle(pg, 150)
            pets = (await api(pg, "GET", "/pets"))["json"]["pets"]
            second = next(q["_id"] for q in pets if q["name"] == "Тест-К")
            await api(
                pg,
                "POST",
                "/medical-records",
                {
                    "pet_id": second,
                    "kind": "visit",
                    "title": "Осмотр",
                    "date": "2026-02-01",
                    "clinic": "Кошачья клиника",
                    "vet": "Мурзина М.М.",
                },
            )

            await pg.goto(f"{BASE}/pets/{first}/medical-records/new?kind=vaccination")
            await settle(pg)
            await pg.get_by_text("Серия, клиника, врач и заметка").click()
            await settle(pg, 200)
            await pg.get_by_text("Клиника", exact=True).click()
            await settle(pg, 300)
            clinics = await pg.locator(".adm-picker-view-column-item").all_inner_texts()
            check(
                "all twelve clinics of this pet are offered, though the card shows ten records",
                all(f"Клиника {i}" in clinics for i in range(1, 13)),
                str(clinics),
            )
            check("and the clinic of the other pet", "Кошачья клиника" in clinics, str(clinics))
            await pg.get_by_role("button", name="Отмена").last.click()
            await settle(pg, 300)
            await pg.evaluate(
                "() => document.querySelectorAll('.adm-popup').forEach(p => { if (getComputedStyle(p).display === 'none') p.remove(); })"
            )
            await pg.get_by_text("Врач", exact=True).click()
            await settle(pg, 300)
            doctors = await pg.locator(".adm-picker-view-column-item").all_inner_texts()
            check(
                "all twelve doctors are offered too",
                all(f"Врач {i}" in doctors for i in range(1, 13)),
                str(doctors),
            )
            check("and the doctor of the other pet", "Мурзина М.М." in doctors, str(doctors))
        finally:
            await drop_pet(pg, first)
            if second:
                await api(pg, "DELETE", f"/pets/{second}")
            await b.close()
    return summary("клиники и врачи: все известные")


asyncio.run(main())
