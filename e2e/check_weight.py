"""The weight screen: «История» in the head, the round «+» to record, and the card follows what the feed records."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        # a scratch dog: an existing weight, then a new one from the section
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
                {"pet_id": pid, "type": "weight", "date": "2026-10-01", "time": "09:00", "fields": {"weight": 12.0}},
            )
            await pg.goto(BASE + f"/pets/{pid}/medical-card/weight")
            await settle(pg)
            check(
                "with a weight there: «История» in the head and the round «+» to record",
                await pg.get_by_role("button", name="История").count() == 1
                and await pg.get_by_role("button", name="Записать вес").count() == 0
                and await pg.locator(".app-fab").count() == 1,
            )
            await pg.screenshot(path="wt_section.png")
            await pg.locator(".app-fab").click()
            await settle(pg, 150)
            check("the «+» opens the feed's weight form", pg.url.endswith("/form/weight"), pg.url.replace(BASE, ""))
            await pg.get_by_label("Вес (кг)").fill("12,4")
            await pg.get_by_role("button", name="Создать").click()
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
            t = await pg.inner_text("body")
            check(
                "the card shows the new weight and the change at once",
                "12,4 кг" in t and "+0,4" in t,
                t[:200].replace(chr(10), " | "),
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("weight section")


asyncio.run(main())
