"""A read-only walk through the signed-in screens of a RUNNING site, for the owner to run with their own account.

It writes nothing: no record, no pet, no setting is created, changed or deleted. It signs in, opens each main screen of the
chosen pet on a phone viewport, and checks that the screen says its own word, shows no text about a failure, does not scroll
sideways and logs no error to the console; then it signs out.

It is for the person who owns the account. The credentials come from the environment and are typed by that person, never by
an assistant (the project rules forbid entering credentials on production):

    PETZY_SMOKE_BASE=https://petzy.duckdns.org PETZY_SMOKE_USER=<login> PETZY_SMOKE_PASSWORD=<password> \\
        .venv/bin/python e2e/prod_smoke.py

It is not part of `e2e/run.py`: the checks there need the local stand and its demo data.
"""

import asyncio
import os
import sys

from playwright.async_api import async_playwright

BASE = os.environ.get("PETZY_SMOKE_BASE", "").rstrip("/")
USER = os.environ.get("PETZY_SMOKE_USER", "")
PASSWORD = os.environ.get("PETZY_SMOKE_PASSWORD", "")

# The screen, and a word it must say. Opened by address, one after another; nothing is clicked that writes.
SCREENS = [
    ("/", ["Лента"]),
    ("/medical-card", ["Медкарта"]),
    ("/medications", ["Лекарства"]),
    ("/documents", ["Документы"]),
    ("/settings", ["Настройки", "Аккаунт"]),
    ("/pets", ["Мои питомцы"]),
    ("/pet-events", ["Типы записей питомца"]),
    ("/help", ["Частые вопросы"]),
]
BROKEN = ("Не удалось загрузить", "Сервер не ответил", "Что-то пошло не так", "Не найдено")

_failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        _failures.append(name)


async def main() -> int:
    if not (BASE and USER and PASSWORD):
        print("Set PETZY_SMOKE_BASE, PETZY_SMOKE_USER and PETZY_SMOKE_PASSWORD (see the top of this file).")
        return 2
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, locale="ru-RU"
        )
        pg = await ctx.new_page()
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto(BASE + "/login")
        await pg.get_by_label("Логин").fill(USER)
        await pg.get_by_label("Пароль").fill(PASSWORD)
        await pg.get_by_role("button", name="Войти").click()
        await pg.wait_for_url(lambda u: "/login" not in u, timeout=20000)
        check("signed in", "/login" not in pg.url, pg.url)
        for route, words in SCREENS:
            await pg.goto(BASE + route)
            await pg.wait_for_load_state("networkidle")
            await pg.wait_for_timeout(600)
            body = await pg.inner_text("body")
            check(f"{route}: says its own word", all(w in body for w in words), body[:120].replace("\n", " | "))
            check(f"{route}: no word of a failure", not any(w in body for w in BROKEN), body[:120].replace("\n", " | "))
            overflow = await pg.evaluate("document.documentElement.scrollWidth - innerWidth")
            check(f"{route}: no sideways scroll", overflow <= 0, f"{overflow}px")
        check("no error in the console", not errors, "; ".join(errors[:3]))
        await pg.goto(BASE + "/settings")
        await pg.get_by_text("Выйти из аккаунта").first.click()
        await pg.get_by_role("button", name="Выйти", exact=True).click()
        await pg.wait_for_url(lambda u: "/login" in u, timeout=20000)
        check("signed out", "/login" in pg.url, pg.url)
        await browser.close()
    print("== prod smoke: " + ("ALL PASS" if not _failures else f"{len(_failures)} FAILED"))
    return 1 if _failures else 0


sys.exit(asyncio.run(main()))
