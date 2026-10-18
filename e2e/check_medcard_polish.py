"""The small rules of the card's parts and of the note to the vet:

- every part of the card adds by its own round «+», and no block repeats it with a button of its own («Записать вес»,
  «Добавить»): two ways to the same record on one screen is one too many; the card's summary has no «+» at all;
- «Прививки и обработки» and «Визиты» ask between two kinds;
- the part names the pet and offers the way to the list of pets when there is more than one;
- the five-clinic cap is said instead of the «+ Добавить клинику» button simply disappearing;
- an answer to «К приёму» that was taken back is not a change, so leaving asks nothing.

Own scratch pet «Тест-М», deleted afterwards; the demo pet is only read.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle

CLINICS = [{"name": f"Клиника {i}", "phone": "+7 701 000 00 00", "doctors": []} for i in range(1, 6)]

# The block's own «Добавить», and not the round «+»: on the parts that ask between two kinds the «+» is
# signed «Добавить» too, so counting by accessible name would count the very button that is meant to stay.
BLOCK_DOORS = """() => [...document.querySelectorAll('main button')]
  .filter((b) => !b.classList.contains('app-fab') && b.textContent.trim() === 'Добавить').length"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        # The pet with records in them: the rule is about a block that has something to put a door on, and
        # an empty block draws none, so the scratch pet of this check would pass it without trying.
        rex = await pg.evaluate("JSON.parse(localStorage.getItem('selectedPetId'))")
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

            # the weight is added by the part's round «+»; the block does not repeat it
            await pg.goto(BASE + f"/pets/{pid}/medical-card/weight")
            await settle(pg)
            check(
                "«Вес»: the round «+» records, and the block has no second «Записать вес»",
                await pg.get_by_role("button", name="Записать вес").count() == 0
                and await pg.locator(".app-fab").count() == 1,
            )
            check(
                "the part names the pet and offers the way to the list",
                "Тест-М" in await pg.inner_text("body")
                and await pg.get_by_role("button", name="Все питомцы").count() == 1,
            )
            await pg.get_by_role("button", name="Все питомцы").click()
            await settle(pg, 150)
            check("it opens the list of pets", pg.url.endswith("/pets"), pg.url.replace(BASE, ""))

            # One way to add on a part: the round «+». The blocks used to carry a «Добавить» of their own, and
            # «Визиты» a list «Ещё можно добавить», all of them opening the same forms the «+» opens. Two ways
            # to one record on one screen: the person reads which of them is the way, and guesses.
            for part, label in (("prevention", "Прививки и обработки"), ("visits", "Визиты")):
                await pg.goto(BASE + f"/pets/{rex}/medical-card/{part}")
                await settle(pg)
                check(f"«{label}» keeps the round «+»", await pg.locator(".app-fab").count() == 1)
                check(
                    f"«{label}»: its blocks carry no second «Добавить»",
                    await pg.evaluate(BLOCK_DOORS) == 0,
                    f"{await pg.evaluate(BLOCK_DOORS)} шт., "
                    + (await pg.inner_text("main"))[:100].replace(chr(10), " | "),
                )

            # The card's summary has no «+»: it showed and hid itself on a scroll, and it added anything at all, while
            # each part adds its own things. A tile is one tap to the part and its «+».
            await pg.goto(BASE + f"/pets/{rex}/medical-card")
            await settle(pg)
            check("the card's summary has no round «+» of its own", await pg.locator(".app-fab").count() == 0)

            # the clinic cap is said, not silently enforced
            saved = await api(
                pg,
                "PUT",
                f"/pets/{pid}/medical-profile",
                {
                    "chip_number": "",
                    "blood_type": "",
                    "allergies": [],
                    "allergies_none_known": True,
                    "conditions": [],
                    "clinics": CLINICS,
                },
            )
            check("five clinics are saved", saved["status"] == 200, str(saved["json"])[:120])
            await pg.goto(BASE + f"/pets/{pid}/medical-profile")
            await settle(pg)
            t = await pg.inner_text("body")
            check(
                "with five clinics the cap is said and the button to add a sixth is not there",
                "Больше пяти клиник" in t and await pg.get_by_role("button", name="+ Добавить клинику").count() == 0,
                t[-160:].replace(chr(10), " | "),
            )

            # an answer taken back is not a change: leaving asks nothing
            await api(pg, "PUT", f"/pets/{pid}/visit-prep", {"complaint": "Кашляет", "checks": {}})
            await pg.goto(BASE + f"/pets/{pid}/medical-card")
            await settle(pg)
            await pg.locator('section:has(h2:text-is("К приёму"))').get_by_role("button", name="Изменить").first.click()
            await settle(pg, 150)
            check("the note opens from the card", pg.url.endswith(f"/pets/{pid}/visit-prep"), pg.url.replace(BASE, ""))
            await pg.get_by_role("button", name="Как обычно").first.click()
            await settle(pg, 150)
            await pg.get_by_role("button", name="Как обычно").first.click()
            await settle(pg, 150)
            await pg.get_by_role("button", name="Отмена").click()
            await settle(pg, 150)
            left = await pg.inner_text("body")
            check(
                "after the answer is taken back, leaving asks nothing",
                "Выйти без сохранения?" not in left and not pg.url.endswith("/visit-prep"),
                left[-160:].replace(chr(10), " | "),
            )
            note = (await api(pg, "GET", f"/pets/{pid}/medical-card"))["json"]["card"]["visit_prep"]
            check(
                "and the saved note is as it was",
                note["complaint"] == "Кашляет" and note["checks"] == {},
                str(note),
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            if pid:
                await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("the small rules of the card's parts and of the note to the vet")


asyncio.run(main())
