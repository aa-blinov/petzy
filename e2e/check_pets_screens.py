"""The pet screens say what a person needs to know before they act.

Three rules this checks, each of which used to be silent:

- «В окне «+»» said «Пока ничего» about a pet whose events had not arrived yet: the screen now
  waits, and says so when the request failed.
- The caption's counter counted the space at the end of the line, while the saved line is
  trimmed: it now counts what is stored.
- Someone a pet is shared with opens the pet's card and finds «События питомца» and «Выйти из
  доступа» outside the dimmed part of the form, so the way out of the screen and into the pet's
  events both take a tap.

Needs the local stack and the demo data. Makes a pet of its own («Тест-М») and removes it.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary
from seed_demo import DEMO_PASSWORD


async def sign_in(pg, user):
    await pg.goto(BASE + "/login")
    await pg.get_by_placeholder("Введите логин").fill(user)
    await pg.get_by_placeholder("Введите пароль").fill(DEMO_PASSWORD)
    await pg.get_by_role("button", name="Войти").click()
    await pg.wait_for_url(lambda u: "/login" not in u, timeout=20000)
    await pg.wait_for_timeout(1500)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        # The co-owner of the seeded demo data: the person the pet is shared with.
        ctx2, other = await new_page(b, width=390, height=844, sw=False)
        await sign_in(other, "family")
        await login(pg, "demo", "Рекс")
        made = await api(pg, "POST", "/pets", {"name": "Тест-М", "species": "dog", "gender": "male"})
        pet_id = made["json"]["pet"]["_id"]
        # The look and the events are about the chosen pet: point the app at the one of this check.
        await pg.evaluate(
            "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id));"
            " localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
            [pet_id, "Тест-М"],
        )
        try:
            # The events of the pet of this check, with the caption's counter on screen.
            await pg.goto(BASE + f"/pets/{pet_id}/edit")
            await pg.wait_for_timeout(2500)
            check(
                "the card opens with this pet's own name",
                await pg.get_by_placeholder("Имя питомца").input_value() == "Тест-М",
            )

            await pg.goto(BASE + "/pet-look")
            await pg.wait_for_timeout(2500)
            # The pet chosen is «Тест-М»: the check made it and left it selected on purpose.
            check(
                "the look screen is open on the pet of this check",
                "Тест-М" in await pg.inner_text("body"),
            )
            await pg.get_by_role("tab", name="Имя").click()
            await pg.wait_for_timeout(1200)
            field = pg.get_by_label("Подпись")
            # A space at the end: the saved line is 13 characters, the typed one 14.
            await field.fill("Хозяин дивана ")
            await pg.wait_for_timeout(600)
            counter = await pg.evaluate(
                "() => { const i = document.getElementById('pet-tagline');"
                " return i && i.nextElementSibling ? i.nextElementSibling.textContent : ''; }",
            )
            check(
                "the counter counts the saved line, not the space at the end of it",
                counter == "13 из 40",
                counter,
            )
            check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
            await pg.screenshot(path="pet_caption.png")

            # The events of this pet: the screen waits for them instead of saying «Пока ничего».
            await pg.goto(BASE + "/pet-events")
            await pg.wait_for_timeout(300)
            early = await pg.inner_text("body")
            await pg.wait_for_timeout(2500)
            late = await pg.inner_text("body")
            check(
                "«Пока ничего» is not said about a pet whose events are still coming",
                "Пока ничего" not in early or "Пока ничего" in late,
                early[:120].replace(chr(10), " | "),
            )
            check(
                "and the events of the pet are on the screen once they are",
                "В окне «+»" in late and "События питомца" in late,
                late[:160].replace(chr(10), " | "),
            )

            # Someone the pet is shared with: the card is dimmed, but the way into the pet's
            # events and the way out of the access must still take a tap. Both sat inside the
            # dimmed part of the form, so `inert` took them away.
            await api(pg, "POST", f"/pets/{pet_id}/share", {"username": "family"})
            await api(other, "POST", f"/pets/{pet_id}/invite/accept")
            await other.goto(BASE + f"/pets/{pet_id}/edit")
            await other.wait_for_timeout(3000)
            t = await other.inner_text("body")
            check(
                "the shared card says who changes it",
                "меняет владелец" in t,
                t[:140].replace(chr(10), " | "),
            )
            events_row = other.get_by_text("События питомца", exact=True)
            check(
                "«События питомца» is offered to someone the pet is shared with",
                await events_row.count() == 1,
                t[:140].replace(chr(10), " | "),
            )
            if await events_row.count() == 1:
                await events_row.click()
                await other.wait_for_timeout(2500)
                check(
                    "and takes that person to the events of the pet",
                    other.url.endswith("/pet-events")
                    and "События меняет владелец питомца" in await other.inner_text("body"),
                    other.url.replace(BASE, ""),
                )
                await other.goto(BASE + f"/pets/{pet_id}/edit")
                await other.wait_for_timeout(2500)
            leave = other.get_by_role("button", name="Выйти из доступа")
            check(
                "«Выйти из доступа» is offered too, and takes a tap",
                await leave.count() == 1 and await leave.is_enabled(),
            )
            await other.close()
        finally:
            # The scratch pet goes with the share on it; nothing of the demo data is touched.
            await api(pg, "DELETE", f"/pets/{pet_id}")
            await ctx2.close()
        await b.close()
    summary("pet screens: what they say before a person acts")


asyncio.run(main())
