"""The weight screen: «Записать вес» next to «История», and the card follows what the feed records."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        # a scratch dog: an existing weight, then a new one from the section
        await pg.goto(BASE + "/pets/new")
        await pg.wait_for_timeout(1200)
        await pg.get_by_role("button", name="Собака").click()
        await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
        await pg.get_by_role("button", name="Добавить", exact=True).click()
        await pg.wait_for_timeout(2200)
        await pg.get_by_role("button", name="Готово").click()
        await pg.wait_for_timeout(800)
        pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
        try:
            await api(
                pg,
                "POST",
                "/events",
                {"pet_id": pid, "type": "weight", "date": "2026-10-01", "time": "09:00", "fields": {"weight": 12.0}},
            )
            await pg.goto(BASE + f"/pets/{pid}/medical-card/weight")
            await pg.wait_for_timeout(1800)
            check(
                "with a weight there: «Записать вес» and «История» in the head",
                await pg.get_by_role("button", name="Записать вес").count() == 1
                and await pg.get_by_role("button", name="История").count() == 1,
            )
            await pg.screenshot(path="wt_section.png")
            await pg.get_by_role("button", name="Записать вес").click()
            await pg.wait_for_timeout(1500)
            check(
                "«Записать вес» opens the feed's weight form", pg.url.endswith("/form/weight"), pg.url.replace(BASE, "")
            )
            await pg.get_by_label("Вес (кг)").fill("12,4")
            await pg.get_by_role("button", name="Создать").click()
            await pg.wait_for_timeout(2200)
            events = (await api(pg, "GET", f"/events?pet_id={pid}&type=weight"))["json"]
            rows = events.get("events") or events.get("items") or []
            check(
                "it is a feed event (the card has no weight of its own)",
                len(rows) == 2,
                str([x["fields"] for x in rows]),
            )
            await pg.goto(BASE + f"/pets/{pid}/medical-card/weight")
            await pg.wait_for_timeout(1800)
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
