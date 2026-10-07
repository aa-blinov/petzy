"""The small rules of the card's parts and of the note to the vet:

- a part of the card where the block already has its own «Записать вес» or «Указать» does not carry the round «+» again;
- «Профилактика» and «Визиты» ask between two kinds and keep the round «+», so their blocks carry no door of their own:
  two ways to the same record on one screen is one too many, and the card itself keeps its «+»;
- the part names the pet and offers the way to the list of pets when there is more than one;
- the five-clinic cap is said instead of the «+ Добавить клинику» button simply disappearing;
- an answer to «К приёму» that was taken back is not a change, so leaving asks nothing.

Own scratch pet «Тест-М», deleted afterwards; the demo pet is only read.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

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
            await pg.wait_for_timeout(1200)
            await pg.get_by_role("button", name="Собака").click()
            await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.wait_for_timeout(2200)
            await pg.get_by_role("button", name="Готово").click()
            await pg.wait_for_timeout(800)
            pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")

            # a part with its own door: the round «+» would only repeat it
            await pg.goto(BASE + f"/pets/{pid}/medical-card/weight")
            await pg.wait_for_timeout(2000)
            check(
                "«Вес»: the block's own «Записать вес» and no second round «+»",
                await pg.get_by_role("button", name="Записать вес").count() == 1
                and await pg.locator(".app-fab").count() == 0,
            )
            check(
                "the part names the pet and offers the way to the list",
                "Тест-М" in await pg.inner_text("body")
                and await pg.get_by_role("button", name="Все питомцы").count() == 1,
            )
            await pg.get_by_role("button", name="Все питомцы").click()
            await pg.wait_for_timeout(1500)
            check("it opens the list of pets", pg.url.endswith("/pets"), pg.url.replace(BASE, ""))

            # One way to add on a part: the round «+». The blocks used to carry a «Добавить» of their own, and
            # «Визиты» a list «Ещё можно добавить», all of them opening the same forms the «+» opens. Two ways
            # to one record on one screen: the person reads which of them is the way, and guesses.
            for part, label in (("prevention", "Профилактика"), ("visits", "Визиты")):
                await pg.goto(BASE + f"/pets/{rex}/medical-card/{part}")
                await pg.wait_for_timeout(2000)
                check(f"«{label}» keeps the round «+»", await pg.locator(".app-fab").count() == 1)
                check(
                    f"«{label}»: its blocks carry no second «Добавить»",
                    await pg.evaluate(BLOCK_DOORS) == 0,
                    f"{await pg.evaluate(BLOCK_DOORS)} шт., "
                    + (await pg.inner_text("main"))[:100].replace(chr(10), " | "),
                )

            # The card itself keeps its «+» too: it is the only way from there to an allergy, a medicine, a
            # weight or a document, so removing it would take the card out of the business of being filled.
            await pg.goto(BASE + f"/pets/{rex}/medical-card")
            await pg.wait_for_timeout(2000)
            check("the card keeps the round «+» in the mode that edits", await pg.locator(".app-fab").count() == 1)

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
            await pg.wait_for_timeout(2000)
            t = await pg.inner_text("body")
            check(
                "with five clinics the cap is said and the button to add a sixth is not there",
                "Больше пяти клиник" in t and await pg.get_by_role("button", name="+ Добавить клинику").count() == 0,
                t[-160:].replace(chr(10), " | "),
            )

            # an answer taken back is not a change: leaving asks nothing
            await api(pg, "PUT", f"/pets/{pid}/visit-prep", {"complaint": "Кашляет", "checks": {}})
            await pg.goto(BASE + f"/pets/{pid}/medical-card")
            await pg.wait_for_timeout(2000)
            await pg.get_by_role("button", name="Изменить").first.click()
            await pg.wait_for_timeout(2000)
            check("the note opens from the card", pg.url.endswith(f"/pets/{pid}/visit-prep"), pg.url.replace(BASE, ""))
            await pg.get_by_role("button", name="Как обычно").first.click()
            await pg.wait_for_timeout(500)
            await pg.get_by_role("button", name="Как обычно").first.click()
            await pg.wait_for_timeout(500)
            await pg.get_by_role("button", name="Отмена").click()
            await pg.wait_for_timeout(1800)
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
