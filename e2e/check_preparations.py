"""Every preparation is one dropdown with a search: a vaccine, a treatment, a medicine. A change of brand keeps one line on the card."""

import asyncio
import re

from common import BASE, api, async_playwright, check, login, new_page, summary, swipe_wheel


async def nav(pg, path):
    await pg.evaluate("p => { history.pushState({}, '', p); dispatchEvent(new PopStateEvent('popstate')) }", path)
    await pg.wait_for_timeout(1500)


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
        card = f"/pets/{pid}/medical-card"
        try:
            old = (
                await api(
                    pg,
                    "POST",
                    "/medical-records",
                    {
                        "pet_id": pid,
                        "kind": "vaccination",
                        "date": "2025-06-01",
                        "title": "Нобивак DHPPi",
                        "next_due": "2026-06-01",
                    },
                )
            )["json"]["id"]
            # ---- a vaccine: a row, a search, no chips
            await pg.goto(BASE + card)
            await pg.wait_for_timeout(1200)
            await nav(pg, f"/pets/{pid}/medical-records/new?kind=vaccination")
            body = await pg.inner_text("body")
            check(
                "the vaccine is a row, with no cloud of chips under it",
                await pg.get_by_role("group", name="Подсказки").count() == 0 and "Выберите или впишите" in body,
            )
            check(
                "no «Найти в списке» button and no extra vaccinations of the day",
                "Найти в списке" not in body and "Ещё прививки в этот день" not in body,
            )
            await pg.get_by_text("Название вакцины").first.click()
            await pg.wait_for_timeout(1000)
            check(
                "the sheet opens with the earlier name first",
                await pg.locator(".prodpick__group-title").first.inner_text() == "Ранее у питомца",
            )
            check(
                "the cursor is in the search",
                await pg.evaluate("document.activeElement && document.activeElement.tagName") == "INPUT",
            )
            await pg.keyboard.type("эурикан")
            await pg.wait_for_timeout(500)
            rows = await pg.locator(".prodpick__row").all_inner_texts()
            check(
                "typing filters the list",
                any("Эурикан DHPPi2" in r for r in rows) and not any("Rabies" in r for r in rows),
                str(rows),
            )
            await pg.locator(".prodpick__row", has_text=re.compile("^Эурикан DHPPi2$")).click()
            await pg.wait_for_timeout(700)
            body = await pg.inner_text("body")
            check("the name is in the row", "Эурикан DHPPi2" in body)
            check(
                "«От чего» is a dropdown row and says Комплексная для собак",
                "От чего" in body
                and "Комплексная для собак" in body
                and await pg.get_by_role("group", name="От чего защищает прививка").count() == 0,
            )
            check("and that it replaces the old entry", "Заменит «Нобивак DHPPi»" in body)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.wait_for_timeout(2200)
            rows = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
            by = {x["_id"]: x for x in rows}
            check(
                "the old brand is history, the new one keeps its protection",
                by[old]["superseded"] and any(x["protects"] == "dhpp" and x["_id"] != old for x in rows),
            )
            # ---- a typed vaccine and a hand choice of the protection from the dropdown
            await pg.goto(BASE + card)
            await pg.wait_for_timeout(1200)
            await nav(pg, f"/pets/{pid}/medical-records/new?kind=vaccination")
            await pg.get_by_text("Название вакцины").first.click()
            await pg.wait_for_timeout(900)
            await pg.keyboard.type("Своя вакцина")
            await pg.wait_for_timeout(400)
            await pg.locator(".prodpick__row--own").click()
            await pg.wait_for_timeout(600)
            check("a typed name is used as typed", "Своя вакцина" in await pg.inner_text("body"))
            await pg.get_by_text("От чего").first.click()
            await pg.wait_for_timeout(700)
            await swipe_wheel(pg, ctx, 0, 1)
            await pg.locator(".adm-picker-header-button", has_text="Готово").last.click()
            await pg.wait_for_timeout(500)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.wait_for_timeout(2200)
            rows = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
            check(
                "saved with the protection chosen in the dropdown",
                any(x["title"] == "Своя вакцина" and x["protects"] == "rabies" for x in rows),
            )
            # ---- a treatment
            await pg.goto(BASE + card)
            await pg.wait_for_timeout(1200)
            await nav(pg, f"/pets/{pid}/medical-records/new?kind=parasite")
            body = await pg.inner_text("body")
            check(
                "the treatment is a row too, no chips",
                "Подсказки" not in body and await pg.get_by_role("group", name="Подсказки").count() == 0,
            )
            await pg.get_by_text("Препарат").first.click()
            await pg.wait_for_timeout(900)
            await pg.keyboard.type("брав")
            await pg.wait_for_timeout(400)
            await pg.locator(".prodpick__row", has_text=re.compile("^Бравекто$")).click()
            await pg.wait_for_timeout(600)
            body = await pg.inner_text("body")
            check("a listed product puts «Блохи и клещи» in", "Блохи и клещи" in body)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.wait_for_timeout(2200)
            rows = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
            check(
                "it saves with its target", any(x["title"] == "Бравекто" and x["target"] == "fleas_ticks" for x in rows)
            )
            # ---- a treatment typed by hand needs its target
            await pg.goto(BASE + card)
            await pg.wait_for_timeout(1200)
            await nav(pg, f"/pets/{pid}/medical-records/new?kind=parasite")
            await pg.get_by_text("Препарат").first.click()
            await pg.wait_for_timeout(900)
            await pg.keyboard.type("Что-то своё")
            await pg.keyboard.press("Enter")
            await pg.wait_for_timeout(600)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.wait_for_timeout(900)
            check(
                "a typed treatment without «От чего» is not saved and says so",
                "Укажите, от чего обработка" in await pg.inner_text("body") and "medical-records/new" in pg.url,
            )
            # ---- a medicine
            await pg.goto(BASE + "/medications")
            await pg.wait_for_timeout(1500)
            await nav(pg, "/medications/new")
            body = await pg.inner_text("body")
            check("the medicine form has no separate «частые лекарства» button", "частых лекарств" not in body)
            await pg.get_by_text("Название", exact=True).first.click()
            await pg.wait_for_timeout(900)
            check(
                "the medicine list opens with a search and groups by purpose",
                await pg.locator(".prodpick__group").count() >= 4,
            )
            await pg.keyboard.type("мелок")
            await pg.wait_for_timeout(400)
            await pg.locator(".prodpick__row", has_text=re.compile("^Мелоксидил$")).click()
            await pg.wait_for_timeout(700)
            body = await pg.inner_text("body")
            check(
                "a known medicine brings its form and strength",
                "Мелоксидил" in body
                and "Суспензия" in body
                and "0,5 мг/мл"
                in await pg.evaluate("[...document.querySelectorAll('input')].map(i => i.value).join('|')"),
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
            await pg.screenshot(path="pk_med.png")
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("one dropdown for every preparation")


asyncio.run(main())
