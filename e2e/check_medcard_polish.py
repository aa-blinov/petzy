"""The small rules of the card's blocks and of the note to the vet:

- every block adds by one door and by one door only: the round «+» in its head, or the link
  under it, never both («Записать вес», «Добавить» beside the «+» would be two ways to the
  same record on one screen);
- the card itself has no «+» of its own;
- the pet is named and the way to the list of pets is offered;
- the five-clinic cap is said instead of the «+ Добавить клинику» button simply disappearing;
- an answer to «К приёму» that was taken back is not a change, so leaving asks nothing.

Own scratch pet «Тест-М», deleted afterwards; the demo pet is only read.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle

CLINICS = [{"name": f"Клиника {i}", "phone": "+7 701 000 00 00", "doctors": []} for i in range(1, 6)]

# How many doors of a block add something to it: the round «+» in its head and the link under
# it that says «Добавить». One block, one door.
WAYS_TO_ADD = """() => {
  const blocks = [...document.querySelectorAll('.medcard__section')];
  return blocks.map((b) => {
    const plus = b.querySelectorAll('.medcard__add').length;
    const link = [...b.querySelectorAll('.medcard__block-links button')].filter(
      (x) => x.textContent.trim() === 'Добавить',
    ).length;
    return { title: b.querySelector('.medcard__section-title')?.textContent ?? '', ways: plus + link };
  });
}"""


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

            # the weight is added by the round «+» of its block; the block does not repeat it
            await pg.goto(BASE + f"/pets/{pid}/medical-card/weight")
            await settle(pg)
            check(
                "«Вес»: the round «+» records, and the block has no second «Записать вес»",
                await pg.get_by_role("button", name="Записать вес").count() == 0
                and await pg.locator(".app-fab").count() == 0
                and await pg.locator("#medcard-weight .medcard__add").count() == 1,
            )
            check(
                "the card names the pet and offers the way to the list",
                "Тест-М" in await pg.inner_text("body")
                and await pg.get_by_role("button", name="Все питомцы").count() == 0,
            )
            await pg.get_by_role("button", name="Тест-М, сменить питомца").click()
            await settle(pg, 150)
            check("the switcher in the head offers the pets", "Выбрать питомца" in await pg.inner_text("body"))
            await pg.keyboard.press("Escape")
            await settle(pg, 150)

            # One way to add in a block: the round «+» in its head, or the link under it.
            await pg.goto(BASE + f"/pets/{rex}/medical-card")
            await settle(pg)
            ways = await pg.evaluate(WAYS_TO_ADD)
            check(
                "no block has two doors to the same record",
                all(w["ways"] <= 1 for w in ways),
                str([w for w in ways if w["ways"] > 1]),
            )
            check(
                "the card itself has no round «+» of its own",
                await pg.locator(".app-fab").count() == 0,
            )

            # The card is stricter than the feed: a plain ground, flat sheets, no portrait.
            ground = await pg.evaluate(
                "() => ({\n"
                "  image: getComputedStyle(document.querySelector('main#main-content')).backgroundImage,\n"
                "  sheet: getComputedStyle(document.querySelector('.medcard__block')).boxShadow,\n"
                "  photo: document.querySelectorAll('.medcard__passport img').length,\n"
                "})"
            )
            check(
                "the card lies on a plain ground: the pet's pattern gives way while it is open",
                ground["image"] == "none",
                ground["image"][:60],
            )
            check(
                "the sheets of the card lie flat: a record is held by its lines, not by a shadow",
                ground["sheet"] == "none",
                ground["sheet"],
            )
            check(
                "the passport has no portrait: the name of the pet is in the bar and the facts in the sheet",
                ground["photo"] == 0,
                f"{ground['photo']} images",
            )

            # The lines of the passport stand close together, as the lines of a record stand: the
            # sheet says facts one after another, not in islands.
            gaps = await pg.evaluate(
                "() => {\n"
                "  const lines = [...document.querySelectorAll('.medcard__passport-body > *')];\n"
                "  return lines.slice(1).map((l, i) => Math.round(l.getBoundingClientRect().top - lines[i].getBoundingClientRect().bottom));\n"
                "}"
            )
            check(
                "the lines of the passport stand close together, without empty islands between them",
                bool(gaps) and all(g <= 6 for g in gaps),
                str(gaps),
            )
            # The number of the chip is copied by a tap, and the tap target is the 44px the house
            # asks for, even though the line is drawn at the size of the text.
            target = await pg.evaluate(
                "() => {\n"
                "  const b = document.querySelector('.medcard__copy');\n"
                "  if (!b) return null;\n"
                "  const r = b.getBoundingClientRect();\n"
                "  const after = getComputedStyle(b, '::after');\n"
                "  return { drawn: Math.round(r.height), target: after.height, top: after.top };\n"
                "}"
            )
            check(
                "the chip is copied by a tap of 44px, and the line under it is not an empty island",
                target is not None
                and int(target["target"].replace("px", "")) >= 44
                and target["top"] in ("0px", "auto"),
                str(target),
            )

            # The vertical rhythm of the document: the gaps between its parts come from the app's
            # one ladder of spacing, not from numbers written by hand.
            rhythm = await pg.evaluate(
                "() => {\n"
                "  const ladder = [0, 2, 4, 8, 12, 16, 24, 32];\n"
                "  const parts = [...document.querySelectorAll('.medcard > *')].filter((el) => el.getBoundingClientRect().height > 0);\n"
                "  return parts.slice(1).map((el, i) => Math.round(el.getBoundingClientRect().top - parts[i].getBoundingClientRect().bottom));\n"
                "}"
            )
            check(
                "the parts of the document stand on the app's ladder of spacing",
                bool(rhythm) and all(g in (0, 2, 4, 8, 12, 16, 24, 32) for g in rhythm),
                str(rhythm),
            )

            # The pressed state of the card's own controls: a 12% layer over the surface, the
            # layer the specification asks for (md.sys.state.pressed-state-layer-opacity).
            door = pg.locator(".medcard__pdf-button").first
            await door.scroll_into_view_if_needed()
            await settle(pg, 150)
            await door.hover()
            await pg.mouse.down()
            await pg.wait_for_timeout(120)
            layer = await door.evaluate("el => getComputedStyle(el).backgroundImage")
            await pg.mouse.up()
            check(
                "the card's own controls take the specification's 12% layer when pressed",
                "0.12" in layer,
                layer[:80],
            )
            plus = pg.locator(".medcard__add").first
            await plus.scroll_into_view_if_needed()
            await settle(pg, 150)
            await plus.hover()
            await pg.mouse.down()
            await pg.wait_for_timeout(120)
            plus_layer = await plus.evaluate("el => getComputedStyle(el).backgroundImage")
            await pg.mouse.up()
            await pg.keyboard.press("Escape")
            await settle(pg, 150)
            check(
                "the round «+» of a block takes it too",
                "0.12" in plus_layer,
                plus_layer[:80],
            )

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
    summary("the small rules of the card's blocks and of the note to the vet")


asyncio.run(main())
