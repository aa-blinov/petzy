"""The blocks of the card: what each one holds, and the door in its head opens what that block is about.

The card used to be eight screens behind eight tiles. It is one document now: the same
blocks, in one scroll, each with the doors of the owner under it. The check reads the demo
pet's card and opens the doors one by one."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary, settle, wait_until

# What each block holds, and the words that say it.
BLOCK_CONTENT = {
    "Здоровье и аллергии": ["Аллергии", "Хронические состояния"],
    "Лекарства": ["Дронтал Плюс"],
    "Вес": ["кг", "замеров"],
    "Прививки и обработки": ["Нобивак"],
    "Визиты и операции": ["осмотр"],
    "Анализы и заключения": ["Анализ крови"],
    "Клиника и врачи": ["Ортовет", "Каримов"],
    "Питание и условия": ["Сухой корм"],
}


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        card = f"/pets/{rex}/medical-card"
        await pg.goto(BASE + card)
        await wait_until(pg, lambda t: "Прививки и обработки" in t)
        await settle(pg)

        for title, wanted in BLOCK_CONTENT.items():
            block = pg.locator(f"section:has(h2:text-is('{title}'))")
            # The heading shows before the block fills itself, so the check waits for the words it
            # is about. A block that never gets them is reported below, not waited out.
            for word in wanted:
                try:
                    await block.get_by_text(word, exact=False).first.wait_for(timeout=10_000)
                except Exception:
                    break
            t = await block.inner_text()
            check(
                f"«{title}» holds its own",
                all(w.lower() in t.lower() for w in wanted),
                str([w for w in wanted if w.lower() not in t.lower()]),
            )

        # the doors under the blocks
        await (
            pg.locator("section:has(h2:text-is('Здоровье и аллергии'))").get_by_role("button", name="Изменить").click()
        )
        await pg.wait_for_url(lambda url: "section=allergies" in url, timeout=10000)
        check(
            "«Изменить» opens the profile at the allergies",
            "section=allergies" in pg.url,
            pg.url.replace(BASE, ""),
        )

        await pg.goto(BASE + card)
        await settle(pg)
        await pg.locator("section:has(h2:text-is('Лекарства'))").get_by_role("button", name="Все лекарства").click()
        await settle(pg, 150)
        check(
            "«Все лекарства» opens the list of medications", pg.url.endswith("/medications"), pg.url.replace(BASE, "")
        )

        await pg.goto(BASE + card)
        await settle(pg)
        await (
            pg.locator("section:has(h2:text-is('Анализы и заключения'))")
            .get_by_role("button", name="Все документы")
            .click()
        )
        await settle(pg, 150)
        check("«Все документы» opens the list of documents", pg.url.endswith("/documents"), pg.url.replace(BASE, ""))

        # the round «+» of a block asks between the two kinds that block is about
        await pg.goto(BASE + card)
        await settle(pg)
        await pg.locator("section:has(h2:text-is('Прививки и обработки'))").locator(".medcard__add").click()
        await settle(pg, 150)
        t = await pg.locator(".adm-popup").last.inner_text()
        check(
            "the «+» of «Прививки и обработки» offers the vaccine and the parasite treatment and nothing else",
            "Прививка" in t and "Обработка от паразитов" in t and "Визит" not in t,
            t.replace(chr(10), " | "),
        )
        await pg.keyboard.press("Escape")
        await settle(pg, 150)

        await pg.locator("section:has(h2:text-is('Визиты и операции'))").locator(".medcard__add").click()
        await settle(pg, 150)
        t = await pg.locator(".adm-popup").last.inner_text()
        check(
            "the «+» of «Визиты и операции» offers the visit and the operation and nothing else",
            "Визит" in t and "Операция" in t and "Прививка" not in t,
            t.replace(chr(10), " | "),
        )
        await pg.keyboard.press("Escape")
        await settle(pg, 150)

        # the clinic of the card calls
        clinic = pg.locator("section:has(h2:text-is('Клиника и врачи'))")
        # The phone comes with the pet's profile, after the block's own heading.
        try:
            await clinic.locator(".medcard__call").first.wait_for(timeout=10_000)
        except Exception:
            pass
        check(
            "the clinic of the card is a call, not a small link",
            await clinic.locator(".medcard__call").count() == 1
            and "Позвонить" in await clinic.inner_text()
            and await clinic.locator(".medcard__call").evaluate("el => getComputedStyle(el).backgroundColor")
            == "rgba(0, 0, 0, 0)",
        )
        check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        await b.close()
    summary("the blocks of the card")


asyncio.run(main())
