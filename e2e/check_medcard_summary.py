"""The medical card as one document: the passport, what is overdue, how ready the card is, the blocks in the order a vet asks in, and the two ways to hand the card over.

Needs the local stack and the demo data (docker compose -p petzy-local ... up, scripts/seed_demo.py)."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary, settle, wait_until

# The blocks of the card, in the order a vet asks in.
BLOCKS = [
    "Здоровье и аллергии",
    "К приёму",
    "Лекарства",
    "Вес",
    "Прививки и обработки",
    "Визиты и операции",
    "Анализы и заключения",
    "Клиника и врачи",
    "Питание и условия",
]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        card = f"/pets/{rex}/medical-card"
        await pg.goto(BASE + card)
        await wait_until(pg, lambda t: "Готовность к приёму" in t)
        await settle(pg)

        check(
            "the card is one document: no mode switch, no tiles and no round «+» of its own",
            await pg.locator(".medcard__mode").count() == 0
            and await pg.locator(".medsum__tile").count() == 0
            and await pg.locator(".app-fab").count() == 0,
        )
        who = await pg.locator(".medcard__pet-facts").inner_text()
        more = await pg.locator(".medcard__pet-more").inner_text()
        words = [w for w in who.replace(",", " ").split() if w[:1].isalpha()]
        rest = [w for w in more.replace(",", " ").split() if w[:1].isalpha()]
        check(
            "the passport says who the pet is, in one case: the species opens the line, the rest is in small letters",
            bool(words) and words[0][:1].isupper() and all(w[:1].islower() for w in words[1:]),
            who.replace(chr(10), " | "),
        )
        check(
            "and the rest of the facts says the same way, in small letters",
            bool(rest) and all(w[:1].islower() for w in rest),
            more.replace(chr(10), " | "),
        )
        check(
            "the name is written once: the bar names the pet, the passport does not repeat it",
            "Рекс" in await pg.locator(".app-navbar").inner_text()
            and "Рекс" not in await pg.locator(".medcard__passport").inner_text(),
            (
                await pg.locator(".app-navbar").inner_text()
                + " || "
                + await pg.locator(".medcard__passport").inner_text()
            )[:150].replace(chr(10), " | "),
        )
        check(
            "the passport carries the weight the doses are counted from",
            "кг" in await pg.locator(".medcard__weight-chip").inner_text(),
            await pg.locator(".medcard__weight-chip").inner_text(),
        )
        check(
            "what is overdue comes before the blocks and says what to do",
            await pg.evaluate(
                "(() => { const z = document.querySelector('.medcard__attention'); const b = document.querySelector('#medcard-risks');"
                " return z && b && z.getBoundingClientRect().top < b.getBoundingClientRect().top; })()"
            )
            and await pg.locator(".medcard__attention-link").count() >= 1,
        )
        check(
            "the overdue says the kind of its own action, not one phrase for everything",
            "Записать повторную прививку" in await pg.locator(".medcard__attention").inner_text()
            and "Записать повторную обработку" in await pg.locator(".medcard__attention").inner_text(),
            (await pg.locator(".medcard__attention").inner_text()).replace(chr(10), " | "),
        )
        check(
            "the readiness says how many of the five are filled",
            "из 5" in await pg.locator(".medcard__ready-count").inner_text(),
            await pg.locator(".medcard__ready-count").inner_text(),
        )
        check(
            "a card that is already filled does not repeat the first-time line",
            await pg.locator(".medcard__lead").count() == 0,
        )
        titles = await pg.locator(".medcard__section-title").all_inner_texts()
        check("the blocks are in the order a vet asks in", titles == BLOCKS, str(titles))
        check(
            "each block adds its own things by the round «+» in its head",
            await pg.locator(".medcard__add").count() >= 6
            and (await pg.locator(".medcard__add").first.get_attribute("aria-label")).startswith("Добавить:"),
            str(await pg.locator(".medcard__add").count()),
        )
        bar = pg.locator(".medcard__bar")
        check(
            "the file and the link for the vet are within reach, without scrolling",
            await bar.count() == 1
            and await pg.get_by_role("button", name="Скачать PDF").count() == 1
            and await pg.get_by_role("button", name="Ссылка для врача").count() == 1
            and await bar.is_visible(),
        )
        bottom = await bar.evaluate("e => Math.round(innerHeight - e.getBoundingClientRect().bottom)")
        check("the bar sits above the tab bar", 0 <= bottom <= 90, f"{bottom}px above the bottom")
        # the address of a part of the card opens the card itself and scrolls to that part
        await pg.goto(BASE + card + "/prevention")
        await settle(pg)
        check(
            "the address of a part opens the card and scrolls to the part",
            await pg.locator("#medcard-prevention").count() == 1
            and await pg.evaluate(
                "(() => { const a = document.querySelector('#medcard-prevention').getBoundingClientRect().top; return a < innerHeight && a > -10; })()"
            ),
            await pg.evaluate(
                "() => Math.round(document.querySelector('#medcard-prevention').getBoundingClientRect().top)"
            ),
        )
        check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        await pg.goto(BASE + card)
        await settle(pg)
        await pg.screenshot(path="c1_document.png")
        await b.close()
    summary("the card as a document")


asyncio.run(main())
