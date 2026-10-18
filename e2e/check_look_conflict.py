"""Two people editing one pet's look: a save made from an old copy is refused, and the person chooses.

The look is the family's to set, so it can be saved from two phones at once. A save from a stale copy must not
overwrite what the other person saved: the screen says so and lets the person take the current look, or keep their
own and save it on top. A throwaway pet is made for the check and deleted afterwards.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle

PET = "qa-look-conflict"


async def stored(pg, pid):
    pets = (await api(pg, "GET", "/pets"))["json"]["pets"]
    return next(p for p in pets if p["_id"] == pid).get("look", {})


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        await login(pg)
        made = await api(pg, "POST", "/pets", {"name": PET, "species": "dog", "gender": "male"})
        pid = made["json"]["pet"]["_id"]
        try:
            await api(pg, "PUT", f"/pets/{pid}/look", {"tagline": "первая", "accent": "sun", "base_version": ""})
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, PET],
            )
            await pg.goto(BASE + "/pet-look")
            await settle(pg)
            await pg.get_by_role("tab", name="Подпись и шрифт").first.click()
            await settle(pg, 150)
            check("the screen shows the caption as saved", await pg.locator("#pet-tagline").input_value() == "первая")

            # The other phone saves a newer look while this screen is open.
            other = await stored(pg, pid)
            await api(
                pg, "PUT", f"/pets/{pid}/look", {"tagline": "вторая", "accent": "sun", "base_version": other["version"]}
            )

            await pg.locator("#pet-tagline").fill("моя")
            await pg.wait_for_timeout(200)
            await pg.get_by_role("button", name="Сохранить").first.click()
            await settle(pg, 150)
            check(
                "a stale save is refused with the question",
                await pg.get_by_text("Оформление изменили в другом месте").count() == 1,
            )
            check("nothing was overwritten yet", (await stored(pg, pid)).get("tagline") == "вторая")

            await pg.locator(".adm-dialog-button", has_text="Показать актуальное").first.click()
            await settle(pg, 150)
            check(
                "«Показать актуальное» brings the other phone's caption into the form",
                await pg.locator("#pet-tagline").input_value() == "вторая",
            )

            # The other phone saves again while this screen is open: the next save from this copy is stale too.
            newer = await stored(pg, pid)
            await api(
                pg, "PUT", f"/pets/{pid}/look", {"tagline": "третья", "accent": "sun", "base_version": newer["version"]}
            )
            await pg.locator("#pet-tagline").fill("моя")
            await pg.wait_for_timeout(200)
            await pg.get_by_role("button", name="Сохранить").first.click()
            await settle(pg, 150)
            check(
                "a second stale save is refused as well",
                await pg.get_by_text("Оформление изменили в другом месте").count() == 1,
            )
            await pg.locator(".adm-dialog-button", has_text="Сохранить моё").first.click()
            await settle(pg, 150)
            check("«Сохранить моё» saves the person's own caption", (await stored(pg, pid)).get("tagline") == "моя")
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
            await ctx.close()
        await browser.close()
    summary("look conflict")


asyncio.run(main())
