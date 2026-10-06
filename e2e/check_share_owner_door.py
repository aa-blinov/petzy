"""The link to a card is a copy: a vet with no account sees the card and no way back. The owner opening their own
link is the same copy, plus one button into the app. The wording of the link settings says the links are shared."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        share_id = None
        try:
            made = await api(pg, "POST", f"/pets/{rex}/medical-card/shares", {"days": 1})
            share_id = made["json"]["share"]["id"]
            url = f"{BASE}/share/medical/{made['json']['token']}"

            # The owner, signed in, opening their own link
            await pg.goto(url)
            await pg.wait_for_timeout(2500)
            t = await pg.inner_text("body")
            door = pg.get_by_role("button", name="Медицинская карта")
            check("the owner is offered the way back into the app", await door.count() == 1, t[:120])
            check("it still says it is a copy", "копия медкарты" in t)
            check(
                "no tab bar and no edit buttons: it stays a copy",
                await pg.locator(".app-tab-bar, .bottom-tab-bar-container").count() == 0
                and await pg.get_by_role("button", name="Ссылка для врача").count() == 0
                and await pg.locator(".app-fab").count() == 0,
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
            await pg.screenshot(path="sh_owner.png")
            await door.click()
            await pg.wait_for_timeout(2500)
            check(
                "the button opens the card in the app",
                pg.url.endswith(f"/pets/{rex}/medical-card"),
                pg.url.replace(BASE, ""),
            )

            # The same link in a browser where nobody is signed in
            ctx2, vet = await new_page(b, width=390, height=844, sw=False)
            await vet.goto(url)
            await vet.wait_for_timeout(2500)
            t = await vet.inner_text("body")
            check(
                "a vet with no account sees the card and no door into the app",
                "Рекс" in t and await vet.get_by_role("button", name="Медицинская карта").count() == 0,
                t[:120].replace(chr(10), " | "),
            )
            check("and is told the way back is closed", "Вернуться в приложение из неё нельзя" in t)
            await ctx2.close()

            # The settings wording: shared links, not the person's own
            await pg.goto(BASE + "/settings")
            await pg.wait_for_timeout(1800)
            row = await pg.get_by_text("Ссылки на медкарту", exact=True).locator("xpath=..").inner_text()
            check(
                "the row says the links are shared and who may use them",
                "Общие ссылки" in row and "любой, у кого есть доступ к питомцу" in row,
                row.replace(chr(10), " | "),
            )
            await pg.get_by_text("Ссылки на медкарту", exact=True).click()
            await pg.wait_for_timeout(1800)
            lead = await pg.locator(".medlinks__lead").inner_text()
            check(
                "the page says a link is opened by anyone who has it, without signing in",
                "Общие ссылки" in lead and "без входа в приложение" in lead and "отозвать любую может любой" in lead,
                lead,
            )
        finally:
            if share_id:
                await api(pg, "DELETE", f"/pets/{rex}/medical-card/shares/{share_id}")
        await b.close()
    summary("share link and the way back")


asyncio.run(main())
