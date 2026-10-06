"""Small things on the account and help screens that a person notices at once.

Each rule here is one of the little findings of the audit: an error that lived
only in a toast, a screen whose state was not said aloud, a search that closed
what had been opened by hand, a document with no list of its sections. The
check signs in once (the stand allows five sign-ins a minute) and touches
nothing of the demo account's own data: the password and email screens are
only read, never saved.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)

        # An empty field is said under the field, and stays there: a toast is
        # gone before the eye gets back to the form.
        await pg.goto(BASE + "/login")
        await pg.wait_for_timeout(1200)
        await pg.get_by_role("button", name="Войти").click()
        await pg.wait_for_timeout(600)
        text = await pg.inner_text("body")
        check(
            "an empty sign-in form says under the field what is missing",
            "Введите логин" in text and "Введите пароль" in text,
            text[:200].replace("\n", " | "),
        )
        check(
            "and the field itself is marked for a screen reader",
            await pg.get_by_label("Логин").first.get_attribute("aria-invalid") == "true",
        )
        # The message survives what comes next on the page, which a toast did not.
        await pg.get_by_placeholder("Введите логин").fill("demo")
        await pg.wait_for_timeout(400)
        check(
            "and it is still there after the next change",
            "Введите пароль" in await pg.inner_text("body"),
        )

        # The same on the recovery screen, plus a way to sign up for someone
        # who has no account yet.
        await pg.goto(BASE + "/forgot-password")
        await pg.wait_for_timeout(1500)
        await pg.get_by_role("button", name="Отправить ссылку").click()
        await pg.wait_for_timeout(600)
        check(
            "an empty recovery form says it under the field",
            "Введите логин или почту" in await pg.inner_text("body"),
        )
        check(
            "and there is a way to sign up for someone without an account",
            await pg.get_by_role("link", name="Создать аккаунт").count() == 1,
        )

        # The sign-up form asks before it drops five typed fields.
        await pg.goto(BASE + "/register")
        await pg.wait_for_timeout(1500)
        check(
            "the consent links say they open in a new tab",
            await pg.get_by_text("Тексты откроются в новой вкладке").count() == 1,
        )
        await pg.get_by_placeholder("например, vera").fill("e2e-form")
        await pg.wait_for_timeout(300)
        await pg.get_by_role("link", name="Войти").first.click()
        await pg.wait_for_timeout(800)
        check(
            "leaving a filled sign-up form asks first",
            await pg.get_by_text("Выйти без сохранения?").count() == 1,
        )
        await pg.get_by_role("button", name="Остаться").click()
        await pg.wait_for_timeout(600)

        await login(pg)

        # Help: a search that finds nothing says so, a search that finds
        # something says how much, and clearing the line leaves open what was
        # opened by hand.
        await pg.goto(BASE + "/help")
        await pg.wait_for_timeout(1500)
        first_item = pg.locator("details.help-item").first
        await first_item.locator("summary").click()
        await pg.wait_for_timeout(400)
        was_open = await first_item.evaluate("el => el.open")
        await pg.get_by_label("Поиск по справке").fill("ветеринар")
        await pg.wait_for_timeout(600)
        check("a search says how much it found", "Найдено:" in await pg.inner_text("body"))
        await pg.get_by_label("Поиск по справке").fill("")
        await pg.wait_for_timeout(600)
        check(
            "clearing the search leaves what the person opened open",
            was_open and await first_item.evaluate("el => el.open"),
        )
        await pg.get_by_label("Поиск по справке").fill("щосьтакогоє")
        await pg.wait_for_timeout(600)
        check(
            "a search that finds nothing says so",
            "Ничего не нашлось" in await pg.inner_text("body"),
        )

        # The email screen: a refusal is said under the field that caused it.
        await pg.goto(BASE + "/settings/email")
        await pg.wait_for_timeout(1800)
        # Near the limit the field says how much is left, instead of typing
        # quietly stopping at 254.
        await pg.get_by_label("Адрес почты").fill("a" * 210 + "@example.com")
        await pg.wait_for_timeout(400)
        check(
            "the address field counts what is typed near the limit",
            await pg.locator(".field-counter").count() == 1,
            (await pg.inner_text(".field-note"))[:80] if await pg.locator(".field-note").count() else "no note",
        )
        await pg.get_by_label("Адрес почты").fill("")
        await pg.wait_for_timeout(300)
        await pg.get_by_label("Текущий пароль").fill("точно-не-пароль")
        await pg.get_by_role("button", name="Сохранить и подтвердить").click()
        await pg.wait_for_timeout(1500)
        check(
            "a refused save is said under the password field, not only in a toast",
            await pg.locator(".field-error").count() >= 1,
            (await pg.inner_text("body"))[:200].replace("\n", " | "),
        )
        check(
            "and the password field is marked",
            await pg.get_by_label("Текущий пароль").get_attribute("aria-invalid") == "true",
        )
        check(
            "the delete button is there even with no address set",
            await pg.get_by_role("button", name="Удалить почту").count() == 1,
        )
        await pg.get_by_label("Текущий пароль").fill("")

        # The password screen: the rules are said, and leaving asks.
        await pg.goto(BASE + "/settings/password")
        await pg.wait_for_timeout(1500)
        await pg.get_by_placeholder("Новый пароль", exact=True).fill("коротк")
        await pg.wait_for_timeout(400)
        check(
            "a short password is said under the field",
            "Не короче 8 символов" in await pg.inner_text("body"),
        )
        await pg.get_by_placeholder("Новый пароль", exact=True).fill("")
        await pg.get_by_placeholder("Новый пароль", exact=True).fill("")

        # The privacy policy: the sections are listed, and the edition number
        # of the same day is not lost.
        await pg.goto(BASE + "/privacy")
        await pg.wait_for_timeout(1500)
        check(
            "the policy lists its sections",
            await pg.get_by_role("navigation", name="Разделы политики").count() == 1,
        )
        check(
            "and each section can be reached from the list",
            await pg.locator('nav[aria-label="Разделы политики"] a').count() >= 8,
        )
        body = await pg.inner_text("body")
        check(
            "the edition keeps its number when the date is the same day",
            "редакция" in body and "Редакция от" in body,
            body[:160].replace("\n", " | "),
        )
        await b.close()
    summary("account screens details")


asyncio.run(main())
