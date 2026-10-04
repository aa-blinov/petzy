"""Settings: «Данные для врача» and «Ссылки на медкарту»: every live link of every pet in one place, taken back with a confirmation."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        pets = (await api(pg, "GET", "/pets"))["json"]["pets"]
        murzik = next(q["_id"] for q in pets if q["name"].startswith("Мурзик"))
        made = []
        try:
            for pid in (rex, murzik):
                r = await api(pg, "POST", f"/pets/{pid}/medical-card/shares", {"days": 7})
                made.append((pid, r["json"]["share"]["id"]))
            await pg.goto(BASE + "/settings")
            await pg.wait_for_timeout(1800)
            body = await pg.inner_text("body")
            check(
                "Settings has a «Медкарта» group with both rows",
                "Данные для врача" in body and "Ссылки на медкарту" in body and "Медкарта" in body,
            )
            await pg.get_by_text("Данные для врача", exact=True).click()
            await pg.wait_for_timeout(1500)
            check(
                "«Данные для врача» opens the profile of the chosen pet",
                "/medical-profile" in pg.url,
                pg.url.replace(BASE, ""),
            )
            await pg.goto(BASE + "/settings")
            await pg.wait_for_timeout(1500)
            await pg.get_by_text("Ссылки на медкарту", exact=True).click()
            await pg.wait_for_timeout(1800)
            check(
                "«Ссылки на медкарту» opens its page",
                pg.url.endswith("/settings/medical-links"),
                pg.url.replace(BASE, ""),
            )
            body = await pg.inner_text("body")
            check(
                "both pets' links are listed under their names",
                "Рекс" in body and "Мурзик" in body and body.count("Отозвать") >= 2,
                body[:200].replace(chr(10), " | "),
            )
            check("each says until when and who made it", "До " in body and "Сделал demo" in body)
            await pg.screenshot(path="ml_page.png")
            # taking one back asks first
            first = pg.get_by_role("button", name="Отозвать").first
            await first.click()
            await pg.wait_for_timeout(700)
            check("it asks before taking a link back", "Отозвать ссылку?" in await pg.inner_text("body"))
            await pg.get_by_role("button", name="Оставить").click()
            await pg.wait_for_timeout(500)
            check(
                "«Оставить» changes nothing",
                (await api(pg, "GET", f"/pets/{rex}/medical-card/shares"))["json"]["shares"] != [],
            )
            await pg.get_by_role("button", name="Отозвать").first.click()
            await pg.wait_for_timeout(700)
            await pg.locator(".adm-dialog-button", has_text="Отозвать").last.click()
            await pg.wait_for_timeout(1500)
            left = [
                len((await api(pg, "GET", f"/pets/{pid}/medical-card/shares"))["json"]["shares"]) for pid, _ in made
            ]
            check("the confirmed one is revoked and the other stays", sorted(left) == [0, 1], str(left))
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
            # the empty state
            for pid, sid in made:
                await api(pg, "DELETE", f"/pets/{pid}/medical-card/shares/{sid}")
            await pg.reload()
            await pg.wait_for_timeout(1800)
            body = await pg.inner_text("body")
            check(
                "with none left it says so and points to the card",
                "Действующих ссылок нет" in body and "Открыть медкарту" in body,
            )
        finally:
            for pid, sid in made:
                await api(pg, "DELETE", f"/pets/{pid}/medical-card/shares/{sid}")
        await b.close()
    summary("settings and links")


asyncio.run(main())
