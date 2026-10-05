"""A required choice with a list: what the row shows is what gets saved.

Ten built-in types start with their first option drawn in the row. The form used to keep an empty value there, so
pressing «Создать» answered «Заполните это поле» under a row that looked filled, and the record could not be saved at
all. This check saves such a record without touching a single list.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
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
            await pg.goto(BASE + "/form/defecation")
            await pg.wait_for_timeout(2200)
            check("the form of «Дефекация» opened", "/form/defecation" in pg.url, pg.url.replace(BASE, ""))
            # What the person reads before saving: both required lists say their first option, nothing is a bare «Выберите».
            check(
                "«Тип стула» shows an option before the person picks anything",
                await pg.get_by_text("Обычный", exact=True).count() >= 1,
                (await pg.inner_text("body"))[:160].replace(chr(10), " | "),
            )
            await pg.get_by_role("button", name="Создать").click()
            await pg.wait_for_timeout(2500)
            body = await pg.inner_text("body")
            check(
                "no «Заполните это поле» under a row that shows an answer",
                "Заполните это поле" not in body,
                body[:200].replace(chr(10), " | "),
            )
            events = (await api(pg, "GET", f"/events?pet_id={pid}&type=defecation"))["json"]
            rows = events.get("events") or events.get("items") or []
            saved = rows[-1]["fields"] if rows else {}
            check(
                "the record is saved, and the drawn choices are the saved ones",
                len(rows) == 1 and saved.get("stool_type") == "Обычный" and saved.get("color") == "Коричневый",
                str(saved),
            )
            await pg.goto(BASE + "/form/asthma")
            await pg.wait_for_timeout(2200)
            # An optional text field stays empty: nothing is written down that the person did not pick.
            check(
                "a required list there too is drawn with its first option",
                await pg.get_by_text("Короткий", exact=True).count() >= 1,
                (await pg.inner_text("body"))[:160].replace(chr(10), " | "),
            )
            await pg.get_by_label("Причина").fill("Пыль")
            await pg.get_by_role("button", name="Создать").click()
            await pg.wait_for_timeout(2500)
            events = (await api(pg, "GET", f"/events?pet_id={pid}&type=asthma"))["json"]
            rows = events.get("events") or events.get("items") or []
            saved = rows[-1]["fields"] if rows else {}
            check(
                "the attack is saved with the drawn duration and the typed reason",
                len(rows) == 1 and saved.get("duration") == "Короткий" and saved.get("reason") == "Пыль",
                str(saved),
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("required choice")


asyncio.run(main())
