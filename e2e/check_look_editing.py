"""Editing a pet's look: Enter in the caption does not save or leave, and «Сбросить оформление» asks first.

The look is shared (the family edits it too), so a half-made caption must not be sent by a stray Enter, and a reset,
which clears the caption and the framing of the photo, must not happen on one tap. A throwaway pet is made for the check
and deleted afterwards; the demo owner's pets are not touched.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle

PET = "qa-look-edit"


async def saved_tagline(pg, pid):
    pets = (await api(pg, "GET", "/pets"))["json"]["pets"]
    return next(p for p in pets if p["_id"] == pid).get("look", {}).get("tagline", "")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        await login(pg)
        made = await api(pg, "POST", "/pets", {"name": PET, "species": "dog", "gender": "female"})
        pid = made["json"]["pet"]["_id"]
        try:
            await api(pg, "PUT", f"/pets/{pid}/look", {"tagline": "старая", "accent": "sun"})
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, PET],
            )
            await pg.goto(BASE + "/pet-look")
            await settle(pg)
            await pg.get_by_role("tab", name="Подпись и шрифт").first.click()
            await settle(pg, 150)
            field = pg.locator("#pet-tagline")
            await field.fill("новая")
            await pg.wait_for_timeout(200)
            check("a changed look says it is not saved yet", await pg.get_by_text("Изменения видны здесь").count() == 1)
            await field.press("Enter")
            await pg.wait_for_timeout(800)
            check("Enter does not leave the screen", "/pet-look" in pg.url, pg.url.replace(BASE, ""))
            check("Enter does not save the caption", await saved_tagline(pg, pid) == "старая")

            await pg.get_by_role("tab", name="Образы").first.click()
            await settle(pg, 150)
            await pg.get_by_role("button", name="Сбросить оформление").first.click()
            await settle(pg, 150)
            check("reset asks first", await pg.get_by_text("Сбросить оформление?").count() == 1)
            await pg.locator(".adm-dialog-button", has_text="Оставить").first.click()
            await settle(pg, 150)
            await pg.get_by_role("tab", name="Подпись и шрифт").first.click()
            await settle(pg, 150)
            check("«Оставить» keeps the caption as typed", await pg.locator("#pet-tagline").input_value() == "новая")

            await pg.get_by_role("tab", name="Образы").first.click()
            await settle(pg, 150)
            await pg.get_by_role("button", name="Сбросить оформление").first.click()
            await settle(pg, 150)
            await pg.locator(".adm-dialog-button", has_text="Сбросить").first.click()
            await settle(pg, 150)
            await pg.get_by_role("tab", name="Подпись и шрифт").first.click()
            await settle(pg, 150)
            check("«Сбросить» clears the caption on the screen", await pg.locator("#pet-tagline").input_value() == "")
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await ctx.close()
        await browser.close()
    summary("look editing")


asyncio.run(main())
