"""The weight on the card: the block of it, its own round «+» to record, and the figure and the change at once."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        # a scratch dog: an existing weight, then a new one from the block
        await pg.goto(BASE + "/pets/new")
        await settle(pg)
        await pg.get_by_role("button", name="Собака").click()
        await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
        await pg.get_by_role("button", name="Добавить", exact=True).click()
        await settle(pg, 150)
        await pg.get_by_role("button", name="Готово").click()
        await settle(pg, 150)
        pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
        try:
            await api(
                pg,
                "POST",
                "/events",
                {
                    "pet_id": pid,
                    "type": "weight",
                    "date": "2026-10-01",
                    "time": "09:00",
                    "fields": {"weight": 12.0},
                    "tz": "Asia/Almaty",
                },
            )
            await pg.goto(BASE + f"/pets/{pid}/medical-card/weight")
            await settle(pg)
            block = pg.locator("#medcard-weight")
            check(
                "with a weight there: the block of it has its own round «+» and no second door",
                await pg.get_by_role("button", name="Записать вес").count() == 0
                and await pg.locator(".app-fab").count() == 0
                and await block.locator(".medcard__add").count() == 1
                and "12 кг" in await block.inner_text(),
                (await block.inner_text()).replace(chr(10), " | "),
            )
            await pg.screenshot(path="wt_section.png")
            await block.locator(".medcard__add").click()
            await settle(pg, 150)
            check("the «+» opens the feed's weight form", pg.url.endswith("/form/weight"), pg.url.replace(BASE, ""))
            await pg.get_by_label("Вес (кг)").fill("12,4")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await settle(pg, 150)
            events = (await api(pg, "GET", f"/events?pet_id={pid}&type=weight"))["json"]
            rows = events.get("events") or events.get("items") or []
            check(
                "it is a feed event (the card has no weight of its own)",
                len(rows) == 2,
                str([x["fields"] for x in rows]),
            )
            await pg.goto(BASE + f"/pets/{pid}/medical-card/weight")
            await settle(pg)
            t = await pg.locator("#medcard-weight").inner_text()
            check(
                "the card shows the new weight and the change at once",
                "12,4 кг" in t and "+0,4" in t,
                t.replace(chr(10), " | "),
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("weight on the card")


asyncio.run(main())
