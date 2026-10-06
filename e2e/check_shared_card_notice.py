"""The page a vet opens by a link: what is said about the link itself, and about what is overdue.

Two small rules are checked here, on a scratch pet of its own:
- the bottom of the page says, in the visitor's own words, that this is the pet's personal data and the link must not be
  passed on (before this it was only in the response headers, which a person never reads);
- the overdue strip on a copy has nothing to press, so it says who can put it right.

The link and the pet are deleted afterwards; the demo pet is not touched.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        share_id = None
        pid = None
        try:
            await pg.goto(BASE + "/pets/new")
            await pg.wait_for_timeout(1200)
            await pg.get_by_role("button", name="Собака").click()
            await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.wait_for_timeout(2200)
            await pg.get_by_role("button", name="Готово").click()
            await pg.wait_for_timeout(800)
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
            share = await api(pg, "POST", f"/pets/{pid}/medical-card/shares", {"days": 1})
            share_id = share["json"]["share"]["id"]
            url = f"{BASE}/share/medical/{share['json']['token']}"

            ctx2, vet = await new_page(b, width=390, height=844, sw=False)
            await vet.goto(url)
            await vet.wait_for_timeout(2500)
            t = await vet.inner_text("body")
            note = await vet.get_by_test_id("share-private").inner_text()
            check(
                "the bottom of the page says what the link is and where it must not go",
                "личные данные питомца" in note and "Не пересылайте ссылку" in note,
                note,
            )
            check(
                "the overdue strip says who can put it right, there being nothing to press",
                "Обновит" in t and "доступ к питомцу" in t and await vet.locator(".medcard__alert button").count() == 0,
                t[:200].replace(chr(10), " | "),
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
