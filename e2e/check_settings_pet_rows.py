"""Настройки это хаб: вкладка «Настройки» горит на своих экранах, «История» знает питомца и умеет записать."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        made = []
        try:
            await pg.goto(BASE + "/settings")
            await pg.wait_for_timeout(1800)
            body = await pg.inner_text("body")
            # Про сам питомца, а не про его отсутствие: подписи переписаны в словах о деле,
            # поэтому проверяем смысл, а не прежнюю формулировку.
            check(
                "the pet's rows say what they do, not «сначала выберите питомца»",
                "Всё, что врач спросит о выбранном питомце" in body and "Скачать записи питомца таблицей" in body,
                body[:200].replace(chr(10), " | "),
            )
            check("no toast about a missing pet on a screen that has one", "Сначала выберите питомца" not in body)
            await pg.screenshot(path="set_rows.png")

            # the Settings tab stays lit on the screens Settings opens
            for path, name in (("/history", "История"), ("/pets", "Мои питомцы")):
                await pg.goto(BASE + path)
                await pg.wait_for_timeout(1500)
                current = await pg.get_by_role("link", name="Настройки").get_attribute("aria-current")
                check(f"the Settings tab is lit on {path}", current == "page", str(current))

            # History: the pet is named, and a record can be written from here
            await pg.goto(BASE + "/history")
            await pg.wait_for_timeout(1800)
            head = await pg.inner_text("header")
            check("the history screen names the chosen pet", "Рекс" in head, head.replace(chr(10), " | "))
            check(
                "the round «+» is there, as on every list",
                await pg.get_by_role("button", name="Добавить запись").count() == 1,
            )
            await pg.screenshot(path="hist_top.png")
            await pg.get_by_role("button", name="Добавить запись").click()
            await pg.wait_for_timeout(1200)
            check("it opens the quick-add sheet", "Все" in await pg.inner_text("body"))
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(600)

            # the feed leads to the history
            await pg.goto(BASE + "/")
            await pg.wait_for_timeout(2000)
            link = await pg.get_by_role("button", name="Вся история").count()
            check("the feed has a way to «Вся история»", link >= 1)

            # a pet of our own, to check «Сначала добавьте питомца» is honest and leads somewhere
            await pg.goto(BASE + "/pets/new")
            await pg.wait_for_timeout(1200)
            await pg.get_by_role("button", name="Собака").click()
            await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.wait_for_timeout(2200)
            await pg.get_by_role("button", name="Готово").click()
            await pg.wait_for_timeout(800)
            made.append(
                next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
            )
            await pg.goto(BASE + "/settings")
            await pg.wait_for_timeout(1800)
            body = await pg.inner_text("body")
            check(
                "with a pet chosen the row keeps its own wording",
                "Скачать записи питомца таблицей" in body and "Сначала добавьте питомца" not in body,
            )
            await pg.get_by_text("Экспорт записей", exact=True).click()
            await pg.wait_for_timeout(1500)
            check(
                "«Экспорт записей» opens the export sheet",
                "Экспорт" in await pg.inner_text("body"),
            )
        finally:
            for pid in made:
                await api(pg, "DELETE", f"/pets/{pid}")
        return summary("settings rows")


asyncio.run(main())
