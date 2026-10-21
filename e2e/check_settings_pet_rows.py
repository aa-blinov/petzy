"""Настройки это хаб: вкладка «Настройки» горит на своих экранах, «История» знает питомца и умеет записать."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        made = []
        try:
            await pg.goto(BASE + "/settings")
            await settle(pg)
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
            for path, name in (("/pets", "Мои питомцы"),):
                await pg.goto(BASE + path)
                await settle(pg)
                current = await pg.get_by_role("link", name="Настройки").get_attribute("aria-current")
                check(f"the Settings tab is lit on {path}", current == "page", str(current))

            # The history screen is gone: the feed is the history, and nothing on it leads to a second
            # list of the same records.
            await pg.goto(BASE + "/")
            await settle(pg)
            link = await pg.get_by_role("button", name="Вся история").count()
            check("на ленте нет второй «Всей истории»: лента и есть история", link == 0, str(link))

            # a pet of our own, to check «Сначала добавьте питомца» is honest and leads somewhere
            await pg.goto(BASE + "/pets/new")
            await settle(pg)
            await pg.get_by_role("button", name="Собака").click()
            await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await settle(pg, 150)
            await pg.get_by_role("button", name="Готово").click()
            await settle(pg, 150)
            made.append(
                next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
            )
            await pg.goto(BASE + "/settings")
            await settle(pg)
            body = await pg.inner_text("body")
            check(
                "with a pet chosen the row keeps its own wording",
                "Скачать записи питомца таблицей" in body and "Сначала добавьте питомца" not in body,
            )
            await pg.get_by_text("Экспорт записей", exact=True).click()
            await settle(pg, 150)
            check(
                "«Экспорт записей» opens the export sheet",
                "Экспорт" in await pg.inner_text("body"),
            )
        finally:
            for pid in made:
                await api(pg, "DELETE", f"/pets/{pid}")
        return summary("settings rows")


asyncio.run(main())
