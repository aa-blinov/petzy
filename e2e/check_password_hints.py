"""Hints before the form is sent: a spent password link, a guessed password
under the field, and the letter that is already on its way.

Nothing here touches the demo account. The letter part needs an account with a
confirmed address, so the check makes a throwaway one («e2e-hint»), confirms
it from the local outbox and deletes it at the end. That costs one sign-up and
two «forgot» requests from this address, so the stand's own limits (five an
hour each) allow a few runs.
"""

import asyncio
import re

from common import BASE, api, async_playwright, check, new_page, summary

GUESSED = "password"  # in the server's list of the most guessed
ORDINARY = "kotik-2026"
THROWAWAY = {"username": "e2e-hint", "password": "e2e-hint-pass-77", "full_name": "Тест", "email": "e2e@example.com"}


def _token_of(letter_subject: str, letters: list) -> str:
    letter = next(one for one in letters if one["subject"] == letter_subject)
    return re.search(r"token=([\w-]+)", letter["text"]).group(1)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        try:
            # The origin the API calls are made from. Nobody signs in here.
            await pg.goto(BASE + "/login")
            await pg.wait_for_timeout(800)
            # The throwaway account the letter part needs.
            made = await api(pg, "POST", "/auth/register", {**THROWAWAY, "privacy_consent": True})
            check("a throwaway account for the letter part is made", made["status"] == 201, str(made["json"])[:160])
            if made["status"] != 201:
                return
            letters = (await api(pg, "GET", "/dev/outbox"))["json"].get("letters", [])
            await api(pg, "POST", "/auth/email/verify", {"token": _token_of("Petzy: подтвердите почту", letters)})

            # A link that cannot work: said at once, no form, a way out.
            await pg.goto(BASE + "/reset-password?token=definitely-not-a-real-token")
            await pg.wait_for_timeout(2000)
            text = await pg.inner_text("body")
            check(
                "a spent link says so right away, and the form is not shown",
                "Ссылка не сработала" in text and (await pg.get_by_placeholder("Новый пароль").count()) == 0,
                text[:160].replace(chr(10), " | "),
            )
            check(
                "it explains why and offers a new letter",
                "устарела" in text and await pg.get_by_role("link", name="Отправить новое письмо").count() == 1,
                text[:160].replace(chr(10), " | "),
            )
            await pg.screenshot(path="reset_dead.png")
            await pg.get_by_role("link", name="Отправить новое письмо").click()
            await pg.wait_for_timeout(1200)
            check("that link goes to «Забыли пароль»", "/forgot-password" in pg.url, pg.url.replace(BASE, ""))

            # A guessed password is said under the field, nothing sent.
            await pg.goto(BASE + "/register")
            await pg.wait_for_timeout(1500)
            field = pg.get_by_placeholder("Придумайте пароль")
            await field.fill(GUESSED)
            await pg.wait_for_timeout(1800)
            text = await pg.inner_text("body")
            check(
                f"typing «{GUESSED}» says under the field that it is a guessed one",
                "Это один из самых частых паролей" in text,
                text[:200].replace(chr(10), " | "),
            )
            await pg.screenshot(path="register_common.png")
            await field.fill(ORDINARY)
            await pg.wait_for_timeout(1800)
            text = await pg.inner_text("body")
            check(
                "an ordinary password clears the hint",
                "Это один из самых частых паролей" not in text,
                text[:200].replace(chr(10), " | "),
            )

            # The same letter twice: said plainly the second time, still offered.
            await pg.goto(BASE + "/forgot-password")
            await pg.wait_for_timeout(1200)
            # По подтверждённой почте: только тому, кто назвал её, сервер и говорит, что письмо уже в пути.
            # По логину ответ одинаков для существующего и несуществующего, иначе форма выдавала бы,
            # у кого здесь есть аккаунт.
            await pg.get_by_placeholder("vera или vera@example.com").fill(THROWAWAY["email"])
            await pg.get_by_role("button", name="Отправить ссылку").click()
            await pg.wait_for_timeout(1500)
            first = await pg.inner_text("body")
            if "Слишком много попыток" in first:
                # The stand allows five requests for a letter per hour per address, and every run of this check
                # spends some of them. On a stand that has already been asked today, the letter part cannot be
                # reached; that is the rule working, not a failure of it.
                print("SKIP the letter part: the stand has spent its five requests for a letter today")
                return summary("password hints")
            check("the first ask says the letter is sent", "отправили на неё ссылку" in first, first[:160])
            await pg.get_by_role("button", name="Отправить ещё раз").click()
            await pg.wait_for_timeout(1800)
            second = await pg.inner_text("body")
            check(
                "asked by the confirmed address, the second ask says the letter is already on its way",
                "уже отправляли недавно" in second,
                second[:200].replace(chr(10), " | "),
            )
            check(
                "and asking again stays possible, not a refusal",
                await pg.get_by_role("button", name="Отправить ещё раз").count() == 1,
                second[:160],
            )
            await pg.screenshot(path="forgot_again.png")

            # The check on opening must not burn the link: the form shows.
            letters = (await api(pg, "GET", "/dev/outbox"))["json"].get("letters", [])
            token = _token_of("Petzy: новый пароль", letters)
            await pg.goto(BASE + f"/reset-password?token={token}")
            await pg.wait_for_timeout(2000)
            check(
                "a working link still opens the form",
                await pg.get_by_role("button", name="Сохранить и войти").count() == 1,
                (await pg.inner_text("body"))[:160].replace(chr(10), " | "),
            )
        finally:
            gone = await api(pg, "DELETE", "/me/account", {"password": THROWAWAY["password"]})
            check("the throwaway account is deleted", gone["status"] == 200, str(gone["json"])[:160])
            await b.close()
    summary("password hints")


asyncio.run(main())
