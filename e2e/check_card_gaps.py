"""What the card says when it has nothing to show: the «Для врача» block is there from the start, the reading mode names the
empty parts, a record opened without a kind asks which kind it is, and the «От чего» of a vaccine is on the form even when the
catalogue did not come. The links screen counts what is taken. A page opened by a link says what it is, and tells a dead link
apart from a connection that did not come through."""

import asyncio
import re

from common import BASE, api, async_playwright, check, login, new_page, summary, wait_until

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
            body = await wait_until(pg, lambda t: "Карта почти пуста" in t)
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
            body = await wait_until(pg, lambda t: "Не заполнено:" in t)
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
            await pg.locator(".medsum__tile").filter(has_text="Документы").first.click()
            body = await wait_until(pg, lambda t: "Все документы" in t)
            check(
                "«Документы» opens its part of the card, with the way to all documents on it",
                pg.url.endswith("/medical-card/documents") and "Все документы" in body,
                pg.url.replace(BASE, ""),
            )
            # the «+» of a part adds what that part is about
            await pg.goto(BASE + f"/pets/{pid}/medical-card/prevention")
            await pg.locator(".app-fab").click()
            body = await wait_until(pg, lambda t: "Прививка" in t)
            check(
                "the «+» of «Профилактика» offers the vaccine and the parasite treatment and nothing else",
                "Прививка" in body and "Обработка от паразитов" in body and "Визит" not in body,
                body[-160:].replace(chr(10), " | "),
            )
            # a record opened without a kind asks which kind
            await pg.goto(BASE + f"/pets/{pid}/medical-records/new")
            body = await wait_until(pg, lambda t: "Не выбрано, что записать" in t)
            check(
                "a record without a kind asks which one instead of failing to load",
                "Не выбрано, что записать" in body and "Не удалось загрузить" not in body,
                body[:160].replace(chr(10), " | "),
            )
            for kind in ("Прививка", "Обработка от паразитов", "Визит", "Операция"):
                check(f"it offers {kind}", kind in body)
            await pg.get_by_text("Прививка", exact=True).first.click()
            await wait_until(pg, lambda t: "Название вакцины" in t)
            check("choosing one opens its form", "?kind=vaccination" in pg.url, pg.url.replace(BASE, ""))
            check(
                "the vaccine form asks for the name",
                await pg.get_by_text("Название вакцины", exact=False).count() >= 1,
                (await pg.inner_text("body"))[:160].replace(chr(10), " | "),
            )
            # the catalogue did not come: the field is still there and says why
            await pg.route("**/api/vaccines/catalog**", lambda route: route.abort())
            await pg.goto(BASE + f"/pets/{pid}/medical-records/new?kind=vaccination")
            body = await wait_until(pg, lambda t: "Список защит не загрузился" in t)
            check(
                "without the catalogue «От чего» is still on the form and offers to try again",
                "От чего" in body
                and "Список защит не загрузился" in body
                and await pg.get_by_role("button", name="Повторить").count() >= 1,
                body[:200].replace(chr(10), " | "),
            )
            await pg.unroute("**/api/vaccines/catalog**")
            # The links screen counts over every pet of the account, so an earlier run's link, or one
            # made by hand, would fail a run that has nothing to do with either. The count is read
            # first and has to grow by one, and this pet's own links are cleared so that its own
            # line says one.
            for old in (await api(pg, "GET", f"/pets/{pid}/medical-card/shares"))["json"]["shares"]:
                await api(pg, "DELETE", f"/pets/{pid}/medical-card/shares/{old['id']}")
            await pg.goto(BASE + "/settings/medical-links")
            was = int(
                re.search(
                    r"Действующих ссылок: (\d+)", await wait_until(pg, lambda t: "Действующих ссылок" in t)
                ).group(1)
            )
            # the links screen counts what is taken of what there may be
            share = await api(pg, "POST", f"/pets/{pid}/medical-card/shares", {"days": 7})
            share_id = share["json"]["share"]["id"]
            await pg.goto(BASE + "/settings/medical-links")
            body = await wait_until(pg, lambda t: "Действующих ссылок" in t)
            check(
                "the links screen counts the live links",
                f"Действующих ссылок: {was + 1}" in body and "Занято 1 из 10 ссылок" in body,
                [line for line in body.split(chr(10)) if "ссылок" in line][:3],
            )
            # a page opened by a link: what it is, and where the file is
            url = BASE + share["json"]["path"]
            ctx2, vet = await new_page(b, width=390, height=844, sw=False)
            await vet.goto(url)
            body = await wait_until(vet, lambda t: "Это копия медкарты" in t)
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
            body = await wait_until(vet, lambda t: "Не удалось загрузить карту" in t)
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
            body = await wait_until(vet, lambda t: "Ссылка не действует" in t or "Не удалось загрузить карту" in t)
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
