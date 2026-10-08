"""The pets in a co-owner's card: each name opens the medical card, and the search for someone to
share with does not offer a person the pet already reaches.

Needs the local stack and the demo data. Makes a pet of its own and removes it."""

import asyncio

from common import BASE, api, async_playwright, check, new_page, summary, wait_until
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
        ctx2, other = await new_page(b, width=390, height=844, sw=False)
        pet_id = None
        try:
            await sign_in(pg, "demo")
            await sign_in(other, "family")
            r = await api(pg, "POST", "/pets", {"name": "Тест-М", "species": "dog", "gender": "male"})
            pet_id = r["json"]["pet"]["_id"]
            # The co-owner accepts, so the pet really is one both of them reach.
            await api(pg, "POST", f"/pets/{pet_id}/share", {"username": "family"})
            await api(other, "POST", f"/pets/{pet_id}/invite/accept")
            # Enough of the card for the «Для врача» block to draw its two buttons: on an empty
            # card it says what is missing instead, and "no link button" would pass for free.
            await api(
                pg,
                "POST",
                "/events",
                {"pet_id": pet_id, "date": "2026-10-01", "time": "10:00", "type": "weight", "fields": {"weight": 12.4}},
            )
            await api(
                pg,
                "POST",
                "/medical-records",
                {"pet_id": pet_id, "date": "2026-09-01", "kind": "vaccination", "title": "Нобивак"},
            )

            profile = await api(other, "GET", "/users/demo/profile")
            pets = profile["json"]["shared_pets"]
            check(
                "the pets in a person's card come as id and name",
                any(isinstance(x, dict) and x.get("id") == pet_id and x.get("name") == "Тест-М" for x in pets),
                str(pets),
            )

            await other.goto(BASE + "/users/demo")
            await other.wait_for_timeout(2500)
            check("the co-owner's card lists the pets in common", "Тест-М" in await other.inner_text("body"))
            link = other.locator("button", has=other.get_by_text("Тест-М", exact=True))
            check("and the name is a way into the medical card", await link.count() == 1)
            await link.first.click()
            await other.wait_for_timeout(3000)
            check(
                "which opens the card",
                other.url.endswith(f"/pets/{pet_id}/medical-card") and "Тест-М" in await other.inner_text("body"),
                other.url.replace(BASE, ""),
            )
            # The card is already open to the co-owner here, so the file is theirs to take. The
            # link is not: it opens the card to anyone with the address, without a sign-in.
            coowner_view = await other.inner_text("body")
            check(
                "the co-owner sees the block that hands the card over",
                "Скачать PDF" in coowner_view,
                [line for line in coowner_view.split(chr(10)) if "Для врача" in line][:2],
            )
            check(
                "but is not offered the link itself",
                "Ссылка для врача" not in coowner_view,
                [line for line in coowner_view.split(chr(10)) if "Ссылка" in line][:2],
            )
            # The owner still gets both doors.
            await pg.goto(BASE + f"/pets/{pet_id}/medical-card")
            await wait_until(pg, lambda t: "Для врача" in t, timeout=10_000)
            check(
                "the owner still has both",
                await pg.get_by_role("button", name="Скачать PDF").count() == 1
                and await pg.get_by_role("button", name="Ссылка для врача").count() == 1,
                (await pg.inner_text("body"))[-160:].replace(chr(10), " | "),
            )
            check("no horizontal scroll", not await other.evaluate("document.documentElement.scrollWidth > innerWidth"))

            # Someone the pet already reaches is not offered again.
            await pg.goto(BASE + f"/pets/{pet_id}/edit")
            await pg.wait_for_timeout(2500)
            await pg.get_by_placeholder("Логин пользователя").fill("family")
            await pg.wait_for_timeout(2500)
            check(
                "a person the pet already reaches is not offered again",
                await pg.get_by_text("У этого человека уже есть доступ").count() == 1,
                (await pg.inner_text("body"))[:120].replace(chr(10), " | "),
            )
            await ctx2.close()
        finally:
            if pet_id:
                await api(pg, "DELETE", f"/pets/{pet_id}")
        await b.close()
    summary("pets in a person's card")


asyncio.run(main())
