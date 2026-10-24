"""The clinic and the doctor of a new record are chosen from a list, not carried over from the last record.

A new vaccination opens with both empty even when an earlier record has a clinic and a doctor; the
clinics and doctors of the profile and of earlier records are in the list, and picking a doctor of
the profile brings his clinic along.

Needs the local stack and the demo data. Makes a scratch pet of its own and removes it.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, settle, summary, swipe_wheel

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
        await login(pg, "demo", "Рекс")
        await pg.goto(BASE + "/pets/new")
        await settle(pg)
        await pg.get_by_role("button", name="Собака").click()
        await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
        await pg.get_by_role("button", name="Добавить", exact=True).click()
        await settle(pg, 150)
        await pg.get_by_role("button", name="Закрыть").last.click()
        await settle(pg, 150)
        pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
        try:
            await api(pg, "PUT", f"/pets/{pid}/medical-profile", PROFILE)
            await api(
                pg,
                "POST",
                "/medical-records",
                {
                    "pet_id": pid,
                    "kind": "vaccination",
                    "title": "Нобивак",
                    "date": "2026-10-01",
                    "clinic": "Айболит",
                    "vet": "Иванова И.И.",
                },
            )
            await pg.goto(f"{BASE}/pets/{pid}/medical-records/new?kind=vaccination")
            await settle(pg)
            await pg.get_by_text("Серия, клиника, врач и заметка").click()
            await settle(pg)
            body = await pg.inner_text("body")
            check(
                "the clinic is not filled in from the last record",
                "Айболит" not in body and "Иванова" not in body,
                body[:200].replace("\n", " | "),
            )
            check(
                "the clinic and the doctor are rows that open a list",
                await pg.get_by_text("Клиника", exact=True).count() > 0,
            )
            await pg.get_by_text("Врач", exact=True).click()
            await settle(pg, 150)
            items = await pg.locator(".adm-picker-view-column-item").all_inner_texts()
            check(
                "the doctors of the profile are in the list",
                "Иванова И.И." in items and "Петров П.П." in items,
                str(items),
            )
            await swipe_wheel(pg, ctx, 0, 2)
            await pg.get_by_role("button", name="Готово").last.click()
            await settle(pg, 150)
            body = await pg.inner_text("body")
            check(
                "the doctor is chosen and brings his clinic",
                "Петров П.П." in body and "Лапка" in body,
                body[-300:].replace("\n", " | "),
            )
        finally:
            await pg.goto(BASE + "/")
            await settle(pg)
            await api(pg, "DELETE", f"/pets/{pid}")
            await b.close()
    return summary("клиника и врач из списка")


asyncio.run(main())
