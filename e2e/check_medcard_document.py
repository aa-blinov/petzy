"""The card read as a document: the alarm, the phone of the clinic, the line of the weight, the sheets over it
and the shape of the loading.

- the one alarm of the card says itself in the alarm's colour: the heading of the block is red, not a quiet title over a coloured box;
- the phone of the clinic is an action in copper on a transparent ground, and the door beside it that changes the clinic is quiet;
- the line of the weight is drawn to the scale of the pet, not to the spread of the series: a change of less than a kilogram
  on a dog of thirty is not a cliff;
- the change of the weight is said once, in the block of the weight, and the passport does not repeat it;
- a sheet over the card names itself;
- the loading of the card has the shape of the card: the passport of the pet and the blocks of the document.

Own scratch pet «Тест-М», deleted afterwards; the demo pet is only read.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        pid = None
        try:
            await pg.goto(BASE + "/pets/new")
            await settle(pg)
            await pg.get_by_role("button", name="Собака").click()
            await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await settle(pg, 150)
            await pg.get_by_role("button", name="Закрыть").last.click()
            await settle(pg, 150)
            pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")

            # The clinic with a phone, so that the block has something to call.
            await api(
                pg,
                "PUT",
                f"/pets/{pid}/medical-profile",
                {
                    "chip_number": "",
                    "blood_type": "",
                    "allergies": [],
                    "allergies_none_known": True,
                    "conditions": [],
                    "clinics": [{"name": "Ортовет", "phone": "+7 727 555 03 04", "doctors": []}],
                },
            )
            # A vaccination whose repeat is long past, so that the card has an alarm to say.
            await api(
                pg,
                "POST",
                "/medical-records",
                {
                    "pet_id": pid,
                    "kind": "vaccination",
                    "title": "Нобивак DHPPi",
                    "date": "2020-05-01",
                    "next_due": "2020-06-01",
                },
            )
            # Two measurements a little apart: the line of them is the weight's trend.
            for day, value in (("2026-08-08", 28.4), ("2026-10-04", 29.3)):
                await api(
                    pg,
                    "POST",
                    "/events",
                    {
                        "pet_id": pid,
                        "type": "weight",
                        "date": day,
                        "time": "09:00",
                        "fields": {"weight": value},
                        "tz": "Asia/Almaty",
                    },
                )

            await pg.goto(BASE + f"/pets/{pid}/medical-card")
            await settle(pg)

            # The alarm: its heading is the alarm's colour.
            alarm = pg.locator(".medcard__attention").first
            heading = alarm.locator(".medcard__zone-title")
            check(
                "the heading of the alarm is in the alarm's colour, not a quiet title over a coloured box",
                await heading.count() == 1
                and await heading.evaluate("el => getComputedStyle(el).color") == "rgb(179, 38, 30)",
                await heading.inner_text() if await heading.count() else "нет заголовка",
            )

            # The alarm is a sheet of its own: the pet's pattern does not show through it.
            ground = await alarm.evaluate(
                "el => { const s = getComputedStyle(el); return s.backgroundColor + '|' + s.backgroundImage; }"
            )
            paint = await alarm.evaluate("el => getComputedStyle(el).backgroundColor")
            check(
                "the alarm is a sheet of its own: the pet's pattern does not show through it",
                paint == "rgb(255, 251, 247)" or paint == "rgb(34, 30, 27)",
                ground,
            )

            # The phone of the clinic: an action in copper, and no slab of colour in the middle of the document.
            clinic = pg.locator("section:has(h2:text-is('Клиника и врачи'))")
            call = clinic.locator(".medcard__call")
            call_style = await call.evaluate(
                "el => { const s = getComputedStyle(el); return s.backgroundColor + '|' + s.color + '|' + s.borderTopColor; }"
            )
            check(
                "the phone of the clinic is a copper action on a transparent ground",
                await call.count() == 1
                and "Позвонить" in await call.inner_text()
                and call_style.startswith("rgba(0, 0, 0, 0)"),
                call_style,
            )
            quiet = clinic.locator(".medcard__link--quiet")
            check(
                "and the door that changes the clinic is quiet",
                await quiet.count() == 1
                and await quiet.evaluate("el => getComputedStyle(el).color") == "rgb(106, 98, 88)",
            )

            # The line of the weight: drawn to the scale of the pet.
            points = await pg.evaluate(
                """() => {
                  const poly = document.querySelector('#medcard-weight .medcard__spark polyline');
                  if (!poly) return null;
                  return poly.getAttribute('points').split(' ').map((p) => Number(p.split(',')[1]));
                }"""
            )
            span = (max(points) - min(points)) if points else None
            check(
                "the line of the weight is drawn to the scale of the pet: a change of a kilogram is not a cliff",
                points is not None and len(points) >= 2 and span is not None and span < 20,
                f"the line covers {span} of the 32 units of the frame" if span is not None else "нет линии",
            )

            # The change of the weight is said once, in the block of the weight.
            delta = await pg.locator("#medcard-weight .medcard__row-sub--meta").first.inner_text()
            passport_text = await pg.locator(".medcard__passport").inner_text()
            check(
                "the change of the weight is said in the block of the weight, and the passport does not repeat it",
                bool(delta.strip()) and delta not in passport_text,
                (delta + " | " + passport_text[:80]).replace(chr(10), " | "),
            )

            # A sheet over the card names itself.
            await pg.locator("#medcard-prevention .medcard__add").click()
            await settle(pg, 200)
            sheet = pg.locator(".adm-popup").last
            sheet_title = sheet.locator(".medcard__sheet-title")
            check(
                "the sheet that asks what to add names itself",
                await sheet_title.count() == 1 and "Что добавить" in await sheet_title.inner_text(),
                (await sheet.inner_text())[:80].replace(chr(10), " | "),
            )
            await pg.keyboard.press("Escape")
            await settle(pg, 150)

            # The loading of the card has the shape of the card.
            async def slow(route):
                await asyncio.sleep(6)
                await route.continue_()

            await pg.route("**/medical-card?*", slow)
            await pg.goto(BASE + f"/pets/{pid}/medical-card")
            await settle(pg, 300)
            sheets = await pg.locator(".card-soft").count()
            check(
                "while the card loads, the page shows the passport and the blocks of the card, not lines of text",
                sheets >= 3,
                f"{sheets} sheets of the card's shape",
            )
            await pg.unroute("**/medical-card?*")

            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            if pid:
                await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("the card read as a document")


asyncio.run(main())
