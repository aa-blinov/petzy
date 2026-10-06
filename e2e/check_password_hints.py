"""Hints before the form is sent: a spent password link, a guessed password
under the field, and the letter that is already on its way.

Nothing here touches the demo account. The letter part needs an account with a
confirmed address, so the check makes a throwaway one («e2e-hint»), confirms
it from the local outbox and deletes it at the end. That costs one sign-up and
two «forgot» requests, and a limit counts per address while every check on the
stand comes from the same one, so the run begins by putting the counters back
to zero (POST /api/dev/reset-limits, the local stand only). Without that the
first run of the hour spent the limits and every later one either skipped or
failed for a reason that had nothing to do with the hints.
"""

import asyncio
import time
import re

from common import BASE, api, async_playwright, check, new_page, summary

GUESSED = "password"  # in the server's list of the most guessed
ORDINARY = "kotik-2026"
# Имя с каждым прогоном своё: сервер считает регистрации (пять в час), а аккаунт от прошлого прогона
# остался бы без подтверждённой почты, и часть про письмо тогда проверяла бы не то, а отказ.
THROWAWAY = {
    "username": f"e2e-hint-{int(time.time())}",
    "password": "e2e-hint-pass-77",
    "full_name": "Тест",
    "email": f"e2e-hint-{int(time.time())}@example.com",
}


def _token_of(letter_subject: str, letters: list, to: str) -> str:
    """The token from the letter addressed to this account, newest first.

    The outbox keeps every letter the stand has sent, so taking the first with
    the right subject can hand back a token from somebody else's account from an
    earlier run: the link then does not work and the check fails for a reason that
    has nothing to do with the rule.
    """
    mine = [one for one in letters if one["subject"] == letter_subject and one.get("to") == to]
    if not mine:
        raise AssertionError(f"нет письма «{letter_subject}» для {to}")
    return re.search(r"token=([\w-]+)", mine[-1]["text"]).group(1)


async def _wait_until(pg, done, timeout: int = 15000) -> str:
    """The page text once `done(text)` holds, or after the wait is up.

    A fixed pause reads a slow answer as a refusal, and that is how a busy stand turned this
    check into one that failed for a reason it never said.
    """
    deadline = time.monotonic() + timeout / 1000
    body = await pg.inner_text("body")
    while time.monotonic() < deadline:
        if done(body):
            return body
        await pg.wait_for_timeout(200)
        body = await pg.inner_text("body")
    return body


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        try:
            # The origin the API calls are made from. Nobody signs in here.
            await pg.goto(BASE + "/login")
            await pg.wait_for_timeout(800)
            # A limit counts per address, and every check on the stand comes from the same one:
            # five letters and five sign-ups an hour are spent by the first run, and the next one
            # starts on a spent limit and checks nothing at all. The counters are put back to zero
            # so every run starts from the same place. On a stand without this endpoint the checks
            # below still run, they just depend on how much of the hour is left.
            reset = await api(pg, "POST", "/dev/reset-limits")
            if reset["status"] != 200:
                print("NOTE this stand has no /api/dev/reset-limits: the hourly limits are not reset between runs")
            # The throwaway account the letter part needs.
            made = await api(pg, "POST", "/auth/register", {**THROWAWAY, "privacy_consent": True})
            made["created"] = made["status"] == 201
            if made["status"] != 201:
                # Стенд считает регистрации: пять в час на адрес, и за день набор успевает их израсходовать.
                # Часть про письмо проверяет свежий аккаунт с подтверждённой почтой, а взять его нечем.
                code = str(made["json"])
                if made["status"] == 429 or (made["status"] == 422 and "занят" in code):
                    print("SKIP the stand's registration limit is spent; the letter part needs a fresh account")
                else:
                    check("a throwaway account for the letter part is made", False, str(made["json"])[:160])
                return summary("password hints")
            check("a throwaway account for the letter part is made", True)
            if made["status"] != 201:
                return
            letters = (await api(pg, "GET", "/dev/outbox"))["json"].get("letters", [])
            await api(
                pg,
                "POST",
                "/auth/email/verify",
                {"token": _token_of("Petzy: подтвердите почту", letters, THROWAWAY["email"])},
            )

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
            text = await _wait_until(pg, lambda t: "Это один из самых частых паролей" in t)
            check(
                f"typing «{GUESSED}» says under the field that it is a guessed one",
                "Это один из самых частых паролей" in text,
                text[:200].replace(chr(10), " | "),
            )
            await pg.screenshot(path="register_common.png")
            await field.fill(ORDINARY)
            text = await _wait_until(pg, lambda t: "Это один из самых частых паролей" not in t)
            check(
                "an ordinary password clears the hint",
                "Это один из самых частых паролей" not in text,
                text[:200].replace(chr(10), " | "),
            )

            # The same letter twice: said plainly the second time, still offered.
            await pg.goto(BASE + "/forgot-password")
            # По подтверждённой почте: только тому, кто назвал её, сервер и говорит, что письмо уже в пути.
            # По логину ответ одинаков для существующего и несуществующего, иначе форма выдавала бы,
            # у кого здесь есть аккаунт.
            await pg.get_by_placeholder("vera или vera@example.com").fill(THROWAWAY["email"])
            await pg.get_by_role("button", name="Отправить ссылку").click()
            # Ждём экрана, а не секунды: пауза вслепую читает медленный ответ как отказ.
            first = await _wait_until(pg, lambda t: "Проверьте почту" in t or "Слишком много попыток" in t)
            # Писем на адрес просят пять в час, а счёт идёт по адресу сети. На стенде с
            # /api/dev/reset-limits сюда не попасть: счётчики только что обнулены. Ветка
            # остаётся для стенда без этого эндпоинта, где норма к этой минуте могла кончиться
            # другими проверками. Тогда сервер прямо говорит, что попробуют позже, и это тоже
            # проверяется: молчаливый отказ был бы хуже.
            if "Слишком много попыток" in first:
                check(
                    "the stand's hourly limit is spent, and the screen says so plainly",
                    "Попробуйте через час" in first or "попробуйте через час" in first,
                    first[:160].replace(chr(10), " | "),
                )
                print("SKIP the letter pair: the stand spent its five letters an hour ago")
                return summary("password hints")
            check(
                "the first ask says the letter is sent",
                "отправили на неё ссылку" in first,
                first[:160].replace(chr(10), " | "),
            )
            again = pg.get_by_role("button", name="Отправить ещё раз")
            await again.click()
            second = await _wait_until(pg, lambda t: "уже отправляли недавно" in t or "Слишком много попыток" in t)
            offered = await again.count() == 1 and await again.is_enabled()
            check(
                "asked by the confirmed address, the second ask says the letter is already on its way",
                "уже отправляли недавно" in second,
                second[:200].replace(chr(10), " | "),
            )
            check(
                "and asking again stays possible, not a refusal",
                offered,
                f"{second[:120]} | кнопка доступна: {offered}",
            )
            await pg.screenshot(path="forgot_again.png")

            # The check on opening must not burn the link: the form shows.
            letters = (await api(pg, "GET", "/dev/outbox"))["json"].get("letters", [])
            token = _token_of("Petzy: новый пароль", letters, THROWAWAY["email"])
            await pg.goto(BASE + f"/reset-password?token={token}")
            await pg.wait_for_timeout(2000)
            check(
                "a working link still opens the form",
                await pg.get_by_role("button", name="Сохранить и войти").count() == 1,
                (await pg.inner_text("body"))[:160].replace(chr(10), " | "),
            )
        finally:
            # Убирать нечего, если аккаунт не был создан: без него и без сессии запрос отвечает 401,
            # и проверка падает на том, чего не делала.
            if made["status"] == 201:
                gone = await api(pg, "DELETE", "/me/account", {"password": THROWAWAY["password"]})
                check("the throwaway account is deleted", gone["status"] == 200, str(gone["json"])[:160])
            await b.close()
    summary("password hints")


asyncio.run(main())
