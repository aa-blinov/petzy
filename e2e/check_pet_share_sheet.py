"""«Поделиться»: the owner shares a pet with the family from the pet card and from the list of pets, in a sheet with its own
«Пригласить»; someone the pet is shared with is not offered the door.

Needs the local stack and the demo data. Makes a pet of its own («Тест-М») and removes it."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, settle, summary
from seed_demo import DEMO_PASSWORD


async def sign_in(pg, user):
    await pg.goto(BASE + "/login")
    await pg.get_by_label("Логин").fill(user)
    await pg.get_by_label("Пароль").fill(DEMO_PASSWORD)
    await pg.get_by_role("button", name="Войти").click()
    await pg.wait_for_url(lambda u: "/login" not in u, timeout=20000)
    await pg.wait_for_function("() => localStorage.getItem('selectedPetId') !== null", timeout=15000)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        ctx2, other = await new_page(b, width=390, height=844, sw=False)
        pet_id = None
        try:
            await login(pg, "demo", "Рекс")
            await sign_in(other, "family")
            made = await api(pg, "POST", "/pets", {"name": "Тест-М", "species": "dog", "gender": "male"})
            pet_id = made["json"]["pet"]["_id"]
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id));"
                " localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pet_id, "Тест-М"],
            )

            # The feed card has the door, and it opens the sheet
            await pg.goto(BASE)
            await settle(pg)
            door = pg.get_by_role("button", name="Поделиться: Тест-М")
            check("the owner sees «Поделиться» on the pet card in the feed", await door.count() == 1)
            await door.click()
            await settle(pg, 300)
            sheet = pg.get_by_role("dialog", name="Поделиться питомцем")
            check(
                "it opens a sheet with the login field and its own button",
                await sheet.get_by_role("textbox", name="Логин человека").count() == 1
                and await sheet.get_by_role("button", name="Пригласить").count() == 1,
            )

            # An empty login is said, not sent
            await sheet.get_by_role("button", name="Пригласить").click()
            await settle(pg, 150)
            check("an empty login is refused in words", "Введите логин человека" in await sheet.inner_text())

            # The invitation goes out at once, without any «Сохранить»
            await sheet.get_by_role("textbox", name="Логин человека").fill("family")
            await sheet.get_by_role("button", name="Пригласить").click()
            await settle(pg, 500)
            invites = (await api(pg, "GET", f"/pets/{pet_id}"))["json"]["pet"].get("share_invites", [])
            check("the invitation was sent at once", "family" in invites, str(invites))
            text = await sheet.inner_text()
            check(
                "the person is listed as «Приглашён»",
                "family" in text and "Приглашён" in text,
                text[-160:].replace(chr(10), " | "),
            )

            # Again: said by name, per person
            await sheet.get_by_role("textbox", name="Логин человека").fill("family")
            await sheet.get_by_role("button", name="Пригласить").click()
            await settle(pg, 300)
            check(
                "a second invitation says the person is already invited",
                "family уже приглашён" in await sheet.inner_text(),
            )

            # The family accepts: the list says «Есть доступ»
            await api(other, "POST", f"/pets/{pet_id}/invite/accept")
            await pg.reload()
            await settle(pg)
            await pg.get_by_role("button", name="Поделиться: Тест-М").click()
            await settle(pg, 300)
            sheet = pg.get_by_role("dialog", name="Поделиться питомцем")
            check("after the answer it says «Есть доступ»", "Есть доступ" in await sheet.inner_text())
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
            await pg.screenshot(path="pshare_sheet.png")

            # Someone the pet is shared with has no door, in the feed or in the list
            await other.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id));"
                " localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pet_id, "Тест-М"],
            )
            await other.goto(BASE)
            await settle(other)
            check(
                "a non-owner sees the card but no «Поделиться» on it",
                "Тест-М" in await other.inner_text("body")
                and await other.get_by_role("button", name="Поделиться: Тест-М").count() == 0,
            )
            await other.goto(BASE + "/pets")
            await settle(other)
            check(
                "and none in the list of pets",
                await other.get_by_role("button", name="Поделиться: Тест-М").count() == 0,
            )

            # The list of pets has the door for the owner
            await pg.keyboard.press("Escape")
            await settle(pg, 300)
            await pg.goto(BASE + "/pets")
            await settle(pg)
            door = pg.get_by_role("button", name="Поделиться: Тест-М")
            check("the owner has «Поделиться» on the row in the list of pets", await door.count() == 1)
            await door.click()
            await settle(pg, 300)
            sheet = pg.get_by_role("dialog", name="Поделиться питомцем")

            # «Убрать» asks for a person who has the access, then closes it
            await sheet.get_by_role("button", name="Убрать доступ: family").click()
            await settle(pg, 300)
            check("taking an access away asks first", "Закрыть доступ" in await pg.inner_text("body"))
            await pg.locator(".adm-dialog-button", has_text="Закрыть доступ").last.click()
            await settle(pg, 500)
            pet = (await api(pg, "GET", f"/pets/{pet_id}"))["json"]["pet"]
            check("the access is closed", "family" not in (pet.get("shared_with") or []), str(pet.get("shared_with")))
        finally:
            if pet_id:
                await api(pg, "DELETE", f"/pets/{pet_id}")
            await ctx2.close()
        await b.close()
    summary("share a pet from its card")


asyncio.run(main())
