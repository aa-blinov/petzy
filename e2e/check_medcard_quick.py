"""The card's tiles only open their parts: no action sits on a tile or in the overdue strip. The actions live in the sections.

Needs the local stack and the demo data (docker compose -p petzy-local ... up, scripts/seed_demo.py)."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary, settle


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        card = f"/pets/{rex}/medical-card"
        await pg.goto(BASE + card)
        await pg.locator(".medsum__tile").first.wait_for(timeout=15000)
        await pg.wait_for_timeout(500)
        check("no tile carries a second button", await pg.locator(".medsum__item button").count() == 0)
        # The rule is for the tiles and the strip. A section of the card carries its own action in its head («К приёму»
        # says «Изменить» once there is a visit prep), and that action belongs to the section, not to a tile.
        tiles_and_strip = pg.locator(".medsum, .medcard__alert")
        check(
            "no «Записать» or «Изменить» button on a tile or in the overdue strip",
            await tiles_and_strip.get_by_role("button", name="Записать", exact=True).count() == 0
            and await tiles_and_strip.get_by_role("button", name="Изменить", exact=True).count() == 0,
        )
        # The strip is the one line that says what to do about a late repeat, so it is the one
        # line that is pressable: a link into the section that holds the record. It also names the
        # others instead of counting them, since "И ещё 1" does not say whether it is a vaccine.
        strip = await pg.locator(".medcard__alert").inner_text()
        check(
            "the overdue strip offers the repeat itself, not the name of a section",
            await pg.locator(".medcard__alert-link").count() == 1 and "Записать повторную прививку" in strip,
            strip.replace("\n", " | "),
        )
        check(
            "the rest of the overdue is named, not just counted",
            "И ещё 1: " in strip,
            strip.replace("\n", " | "),
        )
        # The weight tile by its label: its figure and date are whatever the last weighing was.
        await pg.locator(".medsum__tile", has_text="Вес").first.click()
        await settle(pg, 150)
        check(
            "the weight is recorded inside its section, by its own round «+»",
            await pg.locator(".app-fab").count() == 1,
        )
        await pg.goto(BASE + card + "/risks")
        await settle(pg)
        check(
            "the allergies are changed inside their section",
            await pg.get_by_role("button", name="Изменить", exact=True).count() >= 1,
        )
        await b.close()
    summary("medcard actions in the sections")


asyncio.run(main())
