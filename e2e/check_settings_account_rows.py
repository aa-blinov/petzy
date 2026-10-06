"""Настройки: строки аккаунта говорят своё состояние, тема — где она живёт, у человека есть своя карточка."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        try:
            await pg.goto(BASE + "/settings")
            await pg.get_by_role("heading", name="Настройки").first.wait_for(timeout=15000)
            await pg.wait_for_timeout(1200)
            body = await pg.inner_text("body")
            check("у каждой строки аккаунта есть подпись, а не пустая строка", "Логин: demo" in body, body[:200])
            check("тема сказана как своя к этому устройству", "Сохраняется на этом устройстве" in body)

            # Строка своей карточки: без неё в приложении некуда посмотреть, как тебя видят другие.
            check(
                "есть строка «Мой профиль»",
                await pg.get_by_role("button", name="Мой профиль").count() == 1,
            )
            await pg.get_by_role("button", name="Мой профиль").click()
            await pg.wait_for_timeout(1500)
            check(
                "она открывает твою карточку",
                pg.url.endswith("/users/demo"),
                pg.url.replace(BASE, ""),
            )

            # Пока аккаунт грузится, подпись была одним пробелом: пустая строка под названием читается как
            # «ничего не загрузилось», а не как «ещё грузится». Ответ по /api/me/account задерживается.

            async def slow(route):
                await asyncio.sleep(4)
                await route.continue_()

            await pg.route("**/api/me/account", slow)
            await pg.goto(BASE + "/settings")
            await pg.get_by_role("heading", name="Настройки").first.wait_for(timeout=15000)
            await pg.wait_for_timeout(800)
            check("пока аккаунт грузится, написано «Загружаем»", "Загружаем" in await pg.inner_text("body"))
            await pg.wait_for_timeout(4500)
            check(
                "и потом приходит настоящий логин",
                "Логин: demo" in await pg.inner_text("body"),
            )
            check(
                "у обычного человека есть кнопка удаления аккаунта",
                await pg.get_by_role("button", name="Удалить аккаунт").count() == 1,
            )
            # Список людей остаётся только для администратора: правка формы не открыла его наружу.
            admins = await api(pg, "GET", "/users?page=1")
            check("список людей по-прежнему закрыт для обычного человека", admins["status"] == 403, str(admins)[:160])
            check(
                "нет горизонтальной прокрутки",
                await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0,
            )
        finally:
            await ctx.close()
        await b.close()
    summary("settings account rows")


asyncio.run(main())
