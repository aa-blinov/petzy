"""What the card says when it has nothing to show: the «Для врача» block is there from the start, the reading mode names the
empty parts, a record opened without a kind asks which kind it is, and the «От чего» of a vaccine is on the form even when the
catalogue did not come. The links screen counts what is taken. A page opened by a link says what it is, and tells a dead link
apart from a connection that did not come through."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

PET = "Тест-М"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        # its own empty pet: nothing added, so what the card says is the empty answer
        made = await api(pg, "POST", "/pets", {"name": PET, "species": "dog", "birth_date": "2020-01-01"})
        pid = made["json"]["pet"]["_id"]
        share_id = None
        try:
            card = f"/pets/{pid}/medical-card"
            await pg.goto(BASE + card + "?mode=fill")
            await pg.wait_for_timeout(2200)
            body = await pg.inner_text("body")
            check(
                "an empty card keeps the «Для врача» block and says what it needs",
                "Для врача" in body and "Карта почти пуста" in body,
                body[-200:].replace(chr(10), " | "),
            )
            check(
                "and no PDF of an empty card is offered yet",
                await pg.get_by_role("button", name="Скачать PDF").count() == 0,
            )
            await pg.goto(BASE + card + "?mode=vet")
            await pg.wait_for_timeout(2000)
            body = await pg.inner_text("body")
            check(
                "the reading mode names what is empty in one line",
                "Не заполнено:" in body and "аллергии" in body and "прививки" in body and "вес" in body,
                [line for line in body.split(chr(10)) if "Не заполнено" in line],
            )
            check(
                "and says it before the drugs, not after the whole card",
                await pg.evaluate(
                    "(() => { const n = [...document.querySelectorAll('p')].find(e => e.textContent.includes('Не заполнено'));"
                    " return n.getBoundingClientRect().top < document.querySelector('#medcard-vet-meds').getBoundingClientRect().top; })()"
                ),
            )
            # the documents tile is a part of the card, not a jump out of it
            await pg.goto(BASE + card + "?mode=fill")
            await pg.wait_for_timeout(2000)
            await pg.locator(".medsum__tile").filter(has_text="Документы").first.click()
            await pg.wait_for_timeout(1800)
            body = await pg.inner_text("body")
            check(
                "«Документы» opens its part of the card, with the way to all documents on it",
                pg.url.endswith("/medical-card/documents") and "Все документы" in body,
                pg.url.replace(BASE, ""),
            )
            # the «+» of a part adds what that part is about
            await pg.goto(BASE + f"/pets/{pid}/medical-card/prevention")
            await pg.wait_for_timeout(1800)
            await pg.locator(".app-fab").click()
            await pg.wait_for_timeout(1200)
            body = await pg.inner_text("body")
            check(
                "the «+» of «Профилактика» offers the vaccine and the parasite treatment and nothing else",
                "Прививка" in body and "Обработка от паразитов" in body and "Визит" not in body,
                body[-160:].replace(chr(10), " | "),
            )
            # a record opened without a kind asks which kind
            await pg.goto(BASE + f"/pets/{pid}/medical-records/new")
            await pg.wait_for_timeout(2200)
            body = await pg.inner_text("body")
            check(
                "a record without a kind asks which one instead of failing to load",
                "Не выбрано, что записать" in body and "Не удалось загрузить" not in body,
                body[:160].replace(chr(10), " | "),
            )
            for kind in ("Прививка", "Обработка от паразитов", "Визит", "Операция"):
                check(f"it offers {kind}", kind in body)
            await pg.get_by_text("Прививка", exact=True).first.click()
            await pg.wait_for_timeout(2000)
            check("choosing one opens its form", "?kind=vaccination" in pg.url, pg.url.replace(BASE, ""))
            check(
                "the vaccine form asks for the name",
                await pg.get_by_text("Название вакцины", exact=False).count() >= 1,
                (await pg.inner_text("body"))[:160].replace(chr(10), " | "),
            )
            # the catalogue did not come: the field is still there and says why
            await pg.route("**/api/vaccines/catalog**", lambda route: route.abort())
            await pg.goto(BASE + f"/pets/{pid}/medical-records/new?kind=vaccination")
            await pg.wait_for_timeout(2500)
            body = await pg.inner_text("body")
            check(
                "without the catalogue «От чего» is still on the form and offers to try again",
                "От чего" in body
                and "Список защит не загрузился" in body
                and await pg.get_by_role("button", name="Повторить").count() >= 1,
                body[:200].replace(chr(10), " | "),
            )
            await pg.unroute("**/api/vaccines/catalog**")
            # the links screen counts what is taken of what there may be
            share = await api(pg, "POST", f"/pets/{pid}/medical-card/shares", {"days": 7})
            share_id = share["json"]["share"]["id"]
            await pg.goto(BASE + "/settings/medical-links")
            await pg.wait_for_timeout(2200)
            body = await pg.inner_text("body")
            check(
                "the links screen counts the live links",
                "Действующих ссылок: 1" in body and "Занято 1 из 10 ссылок" in body,
                [line for line in body.split(chr(10)) if "ссылок" in line][:3],
            )
            # a page opened by a link: what it is, and where the file is
            url = BASE + share["json"]["path"]
            ctx2, vet = await new_page(b, width=390, height=844, sw=False)
            await vet.goto(url)
            await vet.wait_for_timeout(2500)
            body = await vet.inner_text("body")
            check("a vet with no account sees the pet", PET in body, body[:120].replace(chr(10), " | "))
            check(
                "it says this is a copy with no way back",
                "Это копия медкарты" in body and "нельзя" in body,
            )
            check(
                "the file is offered up, with the reason to take it now",
                await vet.evaluate(
                    "(() => { const b = [...document.querySelectorAll('button')].find(e => e.innerText.includes('Скачать PDF'));"
                    " const m = document.querySelector('#medcard-vet-meds'); return b.getBoundingClientRect().top < m.getBoundingClientRect().top; })()"
                )
                and "может не быть связи" in body,
            )
            # no connection: not the same as a link that stopped working
            await vet.route("**/api/shared/medical-card/**", lambda route: route.abort())
            await vet.reload()
            await vet.wait_for_timeout(2500)
            body = await vet.inner_text("body")
            check(
                "a lost connection asks to try again and does not blame the link",
                "Не удалось загрузить карту" in body
                and "Ссылка не действует" not in body
                and await vet.get_by_role("button", name="Повторить").count() == 1,
                body[:160].replace(chr(10), " | "),
            )
            await vet.unroute("**/api/shared/medical-card/**")
            # a link that has ended is a different sentence: the server says it is not found
            await api(pg, "DELETE", f"/pets/{pid}/medical-card/shares/{share_id}")
            share_id = None
            await vet.reload()
            await vet.wait_for_timeout(2500)
            body = await vet.inner_text("body")
            check(
                "a link that does not work says so and asks for a new one",
                "Ссылка не действует" in body and "Не удалось загрузить карту" not in body,
                body[:160].replace(chr(10), " | "),
            )
            check(
                "a dead link has no retry that cannot help",
                await vet.get_by_role("button", name="Повторить").count() == 0,
            )
            await ctx2.close()
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            if share_id:
                await api(pg, "DELETE", f"/pets/{pid}/medical-card/shares/{share_id}")
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("the card and what it does not have")


asyncio.run(main())
