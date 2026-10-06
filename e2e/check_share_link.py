"""A link to the card for a vet: made, opened with no sign-in in a clean browser, the PDF, taken back."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        card = f"/pets/{rex}/medical-card"
        await pg.goto(BASE + card + "?mode=vet")
        await pg.wait_for_timeout(1800)
        check(
            "the reading view offers «Ссылка для врача»",
            await pg.get_by_role("button", name="Ссылка для врача").count() == 1,
        )
        await pg.get_by_role("button", name="Ссылка для врача").click()
        await pg.wait_for_timeout(900)
        t = await pg.inner_text("body")
        check("the sheet says what it is and warns", "без входа и только прочитает" in t and "только врачу" in t)
        await pg.get_by_role("button", name="1 день").click()
        await pg.get_by_role("button", name="Создать ссылку").click()
        await pg.wait_for_timeout(1500)
        url = await pg.get_by_test_id("share-url").inner_text()
        check(
            "the link is shown once as an address of this site",
            url.startswith(BASE + "/share/medical/") and len(url) > 60,
            url[:70],
        )
        check("with its end", "Действует до" in await pg.inner_text("body"))
        await pg.screenshot(path="sh_sheet.png")
        # a fresh browser: nobody is signed in
        ctx2, vet = await new_page(b, width=390, height=844, sw=False)
        await vet.goto(url)
        await vet.wait_for_timeout(2500)
        t = await vet.inner_text("body")
        check(
            "a vet with no account sees the card",
            "Рекс" in t and "Нобивак" in t and "Аллергии" in t,
            t[:120].replace(chr(10), " | "),
        )
        check(
            "with no tab bar, no edit buttons and no pet switcher",
            await vet.locator(".app-tab-bar, .bottom-tab-bar-container").count() == 0
            and "Добавить" not in t
            and await vet.locator(".app-fab").count() == 0,
        )
        check(
            "with a PDF and without the link door",
            await vet.get_by_role("button", name="Скачать PDF").count() >= 1
            and await vet.get_by_role("button", name="Ссылка для врача").count() == 0,
        )
        check("it says until when", "Ссылка действует до" in t)
        check("the pet's name is the title of the page", (await vet.locator("h1").all_inner_texts()) == ["Рекс"])
        order = await vet.evaluate(
            "(() => { const top = s => document.querySelector(s)?.getBoundingClientRect().top; return [top('.medcard__stamp'), top('.medcard__alert'), top('.medcard__important')]; })()"
        )
        check(
            "the date and the end of the link and what is overdue come before the allergies",
            all(v is not None for v in order) and order[0] < order[2] and order[1] < order[2],
            str(order),
        )
        check(
            "the one PDF button comes before the blocks that need a connection",
            await vet.evaluate(
                "(() => { const b = [...document.querySelectorAll('button')].find(e => e.innerText.includes('Скачать PDF')); return b.getBoundingClientRect().top < document.querySelector('#medcard-vet-meds').getBoundingClientRect().top; })()"
            ),
        )
        check("no search engines", await vet.locator("meta[name=robots]").count() == 1)
        async with vet.expect_download(timeout=20000) as dl:
            await vet.get_by_role("button", name="Скачать PDF").first.click()
        d = await dl.value
        check("the PDF downloads", d.suggested_filename.endswith(".pdf"), d.suggested_filename)
        await vet.screenshot(path="sh_vet.png")
        # take it back
        await pg.get_by_role("button", name="Отозвать").first.click()
        await pg.wait_for_timeout(1500)
        await vet.reload()
        await vet.wait_for_timeout(2000)
        check(
            "a revoked link says so and shows nothing",
            "Ссылка не действует" in await vet.inner_text("body") and "Нобивак" not in await vet.inner_text("body"),
        )
        await ctx2.close()
        check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        await b.close()
    summary("share link")


asyncio.run(main())
