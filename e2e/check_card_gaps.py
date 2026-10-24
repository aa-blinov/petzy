"""What the card says when it has nothing to show: it says what it is and how it is filled in, the empty parts name
themselves, a record opened without a kind asks which kind it is, and the «От чего» of a vaccine is on the form even when the
catalogue did not come. The links screen counts what is taken. A page opened by a link says what it is, and tells a dead link
apart from a connection that did not come through."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, wait_until

PET = "Тест-М"

# How many doors of a block add something to it: the round «+» in its head and the link under
# it that says «Добавить». One block, one door.
WAYS_TO_ADD = """() => [...document.querySelectorAll('.medcard__section')].map((b) => {
  const plus = b.querySelectorAll('.medcard__add').length;
  const link = [...b.querySelectorAll('.medcard__block-links button')].filter(
    (x) => x.textContent.trim() === 'Добавить',
  ).length;
  return { title: b.querySelector('.medcard__section-title')?.textContent ?? '', ways: plus + link };
})"""


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
            await pg.goto(BASE + card)
            body = await wait_until(pg, lambda t: "Карта почти пуста" in t)
            check(
                "an empty card says what it needs and what will come of it",
                "Карта почти пуста" in body and "ссылка для врача" in body,
                body[-200:].replace(chr(10), " | "),
            )
            check(
                "the PDF of an empty card is on the page but disabled, and the reason is beside it",
                await pg.get_by_role("button", name="Скачать PDF").count() == 1
                and await pg.get_by_role("button", name="Скачать PDF").is_disabled()
                and await pg.get_by_role("button", name="Ссылка для врача").is_disabled(),
            )
            body = await wait_until(pg, lambda t: "Не хватает:" in t)
            check(
                "the card names what is empty in one line",
                "Не хватает:" in body and "аллергии" in body and "прививки" in body and "вес" in body,
                [line for line in body.split(chr(10)) if "Не хватает" in line],
            )
            check(
                "and says it before the drugs, not after the whole card",
                await pg.evaluate(
                    "(() => { const n = [...document.querySelectorAll('p')].find(e => e.textContent.includes('Не хватает'));"
                    " return n.getBoundingClientRect().top < document.querySelector('#medcard-meds').getBoundingClientRect().top; })()"
                ),
            )
            # The first time on the card: it says what the card is and how it is filled in, because
            # nobody has written anything yet and the blocks alone would not say what they are for.
            lead = await pg.locator(".medcard__lead").inner_text()
            check(
                "an empty card says what it is and how it is filled in",
                "врач спросит" in lead and "«+»" in lead,
                lead.replace(chr(10), " | "),
            )
            check(
                "and the line is above the blocks, not under them",
                await pg.evaluate(
                    "(() => { const n = document.querySelector('.medcard__lead');"
                    " return n.getBoundingClientRect().top < document.querySelector('#medcard-meds').getBoundingClientRect().top; })()"
                ),
            )
            # An empty block is not filled, so the door under it does not say «Изменить».
            check(
                "an empty block asks to be filled, not to be changed",
                await pg.locator("#medcard-risks .medcard__block-links button", has_text="Заполнить").count() == 1
                and await pg.locator("#medcard-risks .medcard__block-links button", has_text="Изменить").count() == 0,
                (await pg.locator("#medcard-risks .medcard__block-links").inner_text()).replace(chr(10), " | "),
            )
            # the documents of the card are a block of it, not a jump out of it
            await pg.goto(BASE + card)
            body = await wait_until(pg, lambda t: "Все документы" in t)
            check(
                "«Анализы и заключения» is a block of the card, with the way to all documents under it",
                pg.url.endswith("/medical-card") and "Все документы" in body,
                pg.url.replace(BASE, ""),
            )
            # the «+» of a block adds what that block is about
            await pg.goto(BASE + f"/pets/{pid}/medical-card/prevention")
            await pg.locator("#medcard-prevention .medcard__add").click()
            await wait_until(pg, lambda t: "Прививка" in t)
            sheet = await pg.locator(".adm-popup").last.inner_text()
            check(
                "the «+» of «Прививки и обработки» offers the vaccine and the parasite treatment and nothing else",
                "Прививка" in sheet and "Обработка от паразитов" in sheet and "Визит" not in sheet,
                sheet.replace(chr(10), " | "),
            )
            # An empty block says what is missing and where to put it, rather than a list of doors beside
            # the «+»: with no records of its own the round «+» in its head is the way in.
            for part, missing in (
                ("prevention", "Прививок и обработок пока нет"),
                ("visits", "Визитов и операций пока нет"),
            ):
                await pg.goto(BASE + f"/pets/{pid}/medical-card/{part}")
                body = await wait_until(pg, lambda t: "пока нет" in t)
                ways = await pg.evaluate(WAYS_TO_ADD)
                check(
                    f"an empty «{part}» says what is missing and has one door to put it",
                    missing in body
                    and all(w["ways"] <= 1 for w in ways)
                    and await pg.locator(f"#medcard-{part} .medcard__add").count() == 1,
                    body[:160].replace(chr(10), " | "),
                )
            # a record opened without a kind asks which kind
            await pg.goto(BASE + f"/pets/{pid}/medical-records/new")
            body = await wait_until(pg, lambda t: "Что добавить?" in t)
            check(
                "a record without a kind asks which one instead of failing to load",
                "Что добавить?" in body and "Не удалось загрузить" not in body,
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
            # The count the links screen should show, taken from the server. The screen counts over the pets it has loaded,
            # and for a moment after the page opens it can say «0» before they are in: a wait for the label would take that.
            pets = (await api(pg, "GET", "/pets"))["json"].get("pets", [])
            was = 0
            for listed_pet in pets:
                listed = (await api(pg, "GET", f"/pets/{listed_pet['_id']}/medical-card/shares"))["json"] or {}
                was += len(listed.get("shares", []))
            # the links screen counts what is taken of what there may be
            share = await api(pg, "POST", f"/pets/{pid}/medical-card/shares", {"days": 7})
            share_id = share["json"]["share"]["id"]
            await pg.goto(BASE + "/settings/medical-links")
            body = await wait_until(pg, lambda t: f"Действующих ссылок: {was + 1}" in t)
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
            # The first line of the card says what it is. On the copy of a guest it stops there: the
            # guest cannot write into the card, so it must not be told to.
            vet_lead = await vet.locator(".medcard__lead").inner_text()
            check(
                "the copy of a guest says what the card is and not what to press",
                "врач спросит" in vet_lead and "«+»" not in vet_lead,
                vet_lead.replace(chr(10), " | "),
            )
            check(
                "the file is offered up, with the reason to take it now",
                await vet.evaluate(
                    "(() => { const b = [...document.querySelectorAll('button')].find(e => e.innerText.includes('Скачать PDF'));"
                    " const m = document.querySelector('#medcard-meds'); return b.getBoundingClientRect().top < m.getBoundingClientRect().top; })()"
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
