"""The sign-in screens say what they are and what they will do: a screen title of their own, the way to sign up without waiting for an answer, the server's password rules under the field, a way back from the reset form, and a hand at every form that would otherwise lose what was typed."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)

        # One sign-in for the whole check: the demo login allows five a minute.
        await pg.goto(BASE + "/login")
        await pg.wait_for_timeout(1200)
        h1 = pg.get_by_role("heading", level=1)
        check(
            "the sign-in screen names itself in the h1, not the product",
            (await h1.count()) == 1 and (await h1.inner_text()).strip() == "Вход",
            await h1.inner_text() if await h1.count() else "no h1",
        )
        check(
            "and the tab in the browser reads the same",
            "Вход" in await pg.title(),
            await pg.title(),
        )
        check(
            "«Создать аккаунт» is on the screen without waiting for the status answer",
            await pg.get_by_role("button", name="Создать аккаунт").count() == 1,
        )
        await pg.get_by_role("button", name="Создать аккаунт").click()
        await pg.wait_for_timeout(1500)
        check("it leads to the sign-up form", pg.url.endswith("/register"), pg.url.replace(BASE, ""))

        # The email field is there from the first moment, and the password
        # rules are said before the round trip that would refuse it.
        check(
            "the email field is on the sign-up form right away",
            await pg.get_by_label("Почта").count() >= 1,
        )
        await pg.get_by_placeholder("Придумайте пароль").fill("коротк")
        await pg.get_by_placeholder("Придумайте пароль").blur()
        await pg.wait_for_timeout(300)
        check(
            "a password under 8 characters is refused under the field",
            await pg.get_by_text("Не короче 8 символов").count() >= 1,
        )
        await pg.get_by_placeholder("Придумайте пароль").fill("aaaaaaaa")
        await pg.get_by_placeholder("Придумайте пароль").blur()
        await pg.wait_for_timeout(300)
        check(
            "and so is one with fewer than three different characters",
            await pg.get_by_text("Нужно хотя бы три разных символа").count() >= 1,
        )

        # A reset link without a token is a dead one, and it says so at once.
        await pg.goto(BASE + "/reset-password")
        await pg.wait_for_timeout(1200)
        # The owner decided (docs/ux/_decisions.md): the link is checked when the page opens, and a spent one says so
        # right away with a way to ask for a new letter instead of a form that cannot work.
        check(
            "a reset link without a token says so at once",
            await pg.get_by_text("Ссылка не сработала: она устарела или уже использована").count() == 1,
        )
        check("and the form is not offered", await pg.get_by_label("Новый пароль").count() == 0)
        check(
            "and offers a new letter",
            await pg.get_by_role("link", name="Отправить новое письмо").count() == 1,
        )

        # Recovery asks for the confirmed address by name, next to the field.
        await pg.goto(BASE + "/forgot-password")
        await pg.wait_for_timeout(1500)
        check(
            "recovery says the letter goes to the confirmed address",
            await pg.get_by_text("Письмо придёт на подтверждённый адрес аккаунта").count() == 1,
        )
        check(
            "and there is a way back to the sign-in",
            await pg.get_by_role("link", name="Вернуться ко входу").count() == 1,
        )

        # The help search finds a match by any one word, and shows where.
        await login(pg)
        await pg.goto(BASE + "/help")
        await pg.wait_for_timeout(1500)
        await pg.get_by_label("Поиск по справке").fill("ветеринар напоминание")
        await pg.wait_for_timeout(600)
        t = await pg.inner_text("body")
        check(
            "two words find something when they never appear together",
            "Ничего не нашлось" not in t,
            t[:160].replace("\n", " | "),
        )
        check("and the found words are marked in the text", await pg.locator("mark").count() > 0)

        # Settings → Password: what happens on other devices, and the rules,
        # are said before the save, not after it.
        # Reached the way a person does: through Настройки, so the browser's
        # own back isn't in the middle of the check.
        await pg.goto(BASE + "/settings")
        await pg.wait_for_timeout(1500)
        await pg.get_by_role("button", name="Пароль").first.click()
        await pg.wait_for_timeout(1500)
        check(
            "the password screen says the other devices will be signed out",
            await pg.get_by_text("После смены пароля на других устройствах придётся войти заново").count() == 1,
        )
        check(
            "and spells the rules out",
            await pg.get_by_text("не длиннее 72 байт").count() >= 1,
        )
        await pg.get_by_placeholder("Новый пароль", exact=True).fill("Тест-М-123")
        await pg.get_by_placeholder("Повторите новый пароль").fill("Тест-М-123")
        await pg.wait_for_timeout(300)
        await pg.get_by_role("button", name="Отмена").click()
        await pg.wait_for_timeout(800)
        check(
            "leaving it with three typed passwords asks first",
            await pg.get_by_text("Выйти без сохранения?").count() == 1,
        )
        await pg.get_by_role("button", name="Остаться").click()
        await pg.wait_for_timeout(600)

        # Deleting the account: the confirmation names the pets it will take.
        await pg.goto(BASE + "/settings/delete-account")
        await pg.wait_for_timeout(2000)
        await pg.locator("#delete-account-password").fill("что-то")
        await pg.get_by_role("button", name="Удалить аккаунт", exact=True).click()
        await pg.wait_for_timeout(800)
        dialog = await pg.inner_text(".adm-dialog")
        check(
            "the confirmation says what is deleted with the account, not only «это нельзя отменить»",
            "Удалятся" in dialog and "Рекс" in dialog,
            dialog.replace("\n", " | ")[:160],
        )
        await pg.get_by_role("button", name="Отмена").last.click()
        check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        await b.close()
    summary("auth paths")


asyncio.run(main())
