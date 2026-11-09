"""Two ways into the cabinet that a person without a pet, or without a mouse, used to be stuck in.

1. The consent checkbox at sign-up can be reached and ticked from the keyboard: Tab lands on it and Space ticks it.
   antd-mobile hid the native checkbox with display: none, so Tab skipped it.
2. On the «Кто живёт у вас?» step there is «Посмотреть сначала»: it leaves the onboarding and opens the feed, which
   says it is empty and offers to add a pet. Before, the only way out was the claim that a pet is being shared.

Creates one throwaway account on the local stand and deletes it at the end. Needs the local stack (docker compose -p
petzy-local ... up). Not part of pytest or CI."""

import asyncio
import time

from common import BASE, DEMO_PASSWORD, async_playwright, check, new_page, settle, summary

FOCUS_NOW = "() => { const e = document.activeElement; return e ? (e.tagName + ':' + (e.type || '')) : ''; }"


async def consent_by_keyboard(pg) -> None:
    await pg.goto(BASE + "/register")
    await settle(pg)
    await pg.get_by_label("Логин", exact=True).focus()
    reached = False
    for _ in range(12):
        await pg.keyboard.press("Tab")
        if await pg.evaluate(FOCUS_NOW) == "INPUT:checkbox":
            reached = True
            break
    check("Tab reaches the consent checkbox", reached)
    if not reached:
        return
    await pg.keyboard.press("Space")
    await pg.wait_for_timeout(200)
    ticked = await pg.locator("input[type=checkbox]").evaluate("e => e.checked")
    check("Space ticks the consent from the keyboard", ticked is True)


async def browse_first(pg, username: str) -> None:
    await pg.goto(BASE + "/register")
    await settle(pg)
    await pg.get_by_label("Логин", exact=True).fill(username)
    await pg.get_by_label("Как к вам обращаться", exact=True).fill("Тест Просмотр")
    await pg.get_by_label("Почта", exact=True).fill("browse@example.test")
    await pg.get_by_label("Пароль", exact=True).fill(DEMO_PASSWORD)
    await pg.get_by_label("Пароль ещё раз", exact=True).fill(DEMO_PASSWORD)
    await pg.get_by_text("Даю согласие на обработку").click()
    await pg.get_by_role("button", name="Создать аккаунт").click()
    await pg.wait_for_url(lambda u: "/welcome" in u, timeout=20000)
    await settle(pg)
    await pg.get_by_role("button", name="Пропустить").click()
    await settle(pg)
    await pg.get_by_role("button", name="Посмотреть сначала").wait_for(timeout=8000)
    check("the species step offers «Посмотреть сначала»", True)
    await pg.get_by_role("button", name="Посмотреть сначала").click()
    await settle(pg)
    await pg.wait_for_timeout(600)
    body = await pg.locator("body").inner_text()
    check(
        "it opens the feed, which says the feed is empty and offers to add a pet",
        "Здесь будут ваши питомцы" in body and "Добавить питомца" in body and "Кто живёт у вас" not in body,
        body[:120].replace("\n", " | "),
    )


async def delete_account(pg, username: str) -> None:
    await pg.goto(BASE + "/settings/delete-account")
    await settle(pg)
    await pg.get_by_label("Пароль").fill(DEMO_PASSWORD)
    await pg.get_by_role("button", name="Удалить аккаунт").click()
    await pg.wait_for_timeout(1000)
    dialog = pg.get_by_role("dialog")
    if await dialog.count():
        await dialog.get_by_role("button", name="Удалить").first.click()
    await pg.wait_for_timeout(2000)
    await settle(pg)
    check("the throwaway account is deleted", "Аккаунт удалён" in await pg.locator("body").inner_text(), username)


async def main():
    username = "tbrowse" + str(int(time.time()))[-6:]
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        try:
            await consent_by_keyboard(pg)
            await browse_first(pg, username)
        finally:
            try:
                await delete_account(pg, username)
            except Exception as exc:  # keep the report honest if the account could not be removed
                check("the throwaway account is deleted", False, f"{type(exc).__name__}: {str(exc)[:120]} ({username})")
            await ctx.close()
            await b.close()
    summary("signup keyboard and browse first")


asyncio.run(main())
