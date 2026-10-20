"""The top of the card says who the pet is and nothing else: the doors of the owner live in the blocks, and the one pressable line of the top is the repeat of what is overdue.

Needs the local stack and the demo data (docker compose -p petzy-local ... up, scripts/seed_demo.py)."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary, settle, wait_until


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        card = f"/pets/{rex}/medical-card"
        await pg.goto(BASE + card)
        await wait_until(pg, lambda t: "Готовность к приёму" in t)
        await settle(pg)

        passport = pg.locator(".medcard__passport")
        check(
            "the passport carries no door to another screen, only the copy of the chip",
            await passport.locator("a").count() == 0 and await passport.get_by_role("button").count() <= 1,
            (await passport.inner_text()).replace(chr(10), " | "),
        )
        check(
            "the doors of the owner are in the blocks: the round «+» of a head and the links under a block",
            await pg.locator(".medcard__section .medcard__add").count() >= 6
            and await pg.locator(".medcard__block-links").count() >= 4,
            str(await pg.locator(".medcard__block-links").count()),
        )
        check(
            "the top of the card has no round «+» of its own",
            await pg.locator(".medcard__passport .medcard__add").count() == 0
            and await pg.locator(".app-fab").count() == 0,
        )
        # what is overdue is the one pressable line of the top, and it says the kind of its own action
        zone = pg.locator(".medcard__attention")
        check(
            "the overdue block offers the repeat itself, not the name of a section",
            await zone.locator(".medcard__attention-link").count() >= 1
            and "Записать повторную прививку" in await zone.inner_text(),
            (await zone.inner_text()).replace(chr(10), " | "),
        )
        titles = await zone.locator(".medcard__attention-title").all_inner_texts()
        check(
            "the rest of the overdue is named, not just counted",
            len(titles) >= 2 and all(t.strip() for t in titles),
            str(titles),
        )
        # the weight is recorded in its own block, by its own round «+»
        await pg.goto(BASE + card + "/weight")
        await settle(pg)
        check(
            "the weight is recorded inside its block, by its own round «+»",
            await pg.locator("#medcard-weight .medcard__add").count() == 1,
        )
        await pg.goto(BASE + card + "/risks")
        await settle(pg)
        check(
            "the allergies are changed inside their block",
            await pg.locator("#medcard-risks .medcard__block-links").get_by_role("button", name="Изменить").count()
            == 1,
        )
        await b.close()
    summary("medcard actions in the blocks")


asyncio.run(main())
