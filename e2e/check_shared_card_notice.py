"""The page a vet opens by a link: what is said about the link itself, and about what is overdue.

Two small rules are checked here, on a scratch pet of its own:
- the bottom of the page says, in the visitor's own words, that this is the pet's personal data and the link must not be
  passed on (before this it was only in the response headers, which a person never reads);
- the overdue strip on a copy has nothing to press, so it says who can put it right.

The link and the pet are deleted afterwards; the demo pet is not touched.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        share_id = None
        pid = None
        try:
            await pg.goto(BASE + "/pets/new")
            await settle(pg)
            await pg.get_by_role("button", name="Собака").click()
            await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await settle(pg, 150)
            await pg.get_by_role("button", name="Готово").click()
            await settle(pg, 150)
            pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
            # a vaccination whose repeat is long past, so the card has something overdue to say
            made_rec = await api(
                pg,
                "POST",
                "/medical-records",
                {
                    "pet_id": pid,
                    "kind": "vaccination",
                    "title": "Бешенство",
                    "date": "2020-05-01",
                    "next_due": "2020-06-01",
                },
            )
            check("the scratch record is saved", made_rec["status"] == 201, str(made_rec["json"])[:120])
            # and a second one, so that the note about who can put it right is said once and not once per record
            await api(
                pg,
                "POST",
                "/medical-records",
                {
                    "pet_id": pid,
                    "kind": "parasite",
                    "title": "Бравекто",
                    "target": "fleas_ticks",
                    "date": "2020-04-01",
                    "next_due": "2020-05-01",
                },
            )
            share = await api(pg, "POST", f"/pets/{pid}/medical-card/shares", {"days": 1})
            share_id = share["json"]["share"]["id"]
            url = f"{BASE}/share/medical/{share['json']['token']}"

            ctx2, vet = await new_page(b, width=390, height=844, sw=False)
            await vet.goto(url)
            await settle(vet)
            t = await vet.inner_text("body")
            note = await vet.get_by_test_id("share-private").inner_text()
            check(
                "the bottom of the page says what the link is and where it must not go",
                "личные данные питомца" in note and "Не пересылайте ссылку" in note,
                note,
            )
            check(
                "the overdue block says who can put it right, there being nothing to press",
                "Обновит" in t
                and "доступ к питомцу" in t
                and await vet.locator(".medcard__attention button, .medcard__attention a").count() == 0,
                t[:200].replace(chr(10), " | "),
            )
            check(
                "and it says it once, under the list, and not once under every overdue record",
                await vet.locator(".medcard__attention-note").count() == 1
                and await vet.locator(".medcard__attention-item").count() >= 2,
                f"{await vet.locator('.medcard__attention-item').count()} overdue, "
                f"{await vet.locator('.medcard__attention-note').count()} notes",
            )
            title = (await vet.locator("h1").inner_text()).strip()
            passport = await vet.locator(".medcard__passport").inner_text()
            check(
                "the copy says what it is: «Медкарта» stands over the name of the pet",
                "Медкарта" in await vet.locator(".screen-head").inner_text() and title == "Тест-М",
                (await vet.locator(".screen-head").inner_text()).replace(chr(10), " | "),
            )
            check(
                "and the name is written once: the title names the pet, the passport does not repeat it",
                bool(title) and title not in passport,
                (title + " | " + passport[:60]).replace(chr(10), " | "),
            )
            check(
                "the link ends with a date written the way the app writes it",
                "Ссылка действует до " in t and ", " in t.split("Ссылка действует до ")[1][:20],
                t.split("Ссылка действует до ")[1][:40] if "Ссылка действует до " in t else t[:80],
            )
            check("no horizontal scroll", await vet.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
            await vet.screenshot(path="sh_notice.png")
            await ctx2.close()
        finally:
            if share_id and pid:
                await api(pg, "DELETE", f"/pets/{pid}/medical-card/shares/{share_id}")
            if pid:
                await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("the notice at the bottom of a shared card")


asyncio.run(main())
