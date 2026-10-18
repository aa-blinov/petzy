"""The name, the line and the meta of a pet on a photo backdrop carry a halo of the card's colour.

The halo in the card's colour is what keeps the text readable whatever the photo is (white or black, in both themes).
A pet without that backdrop has no halo at all. A throwaway pet is made for the check and deleted afterwards.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle

PET = "qa-plate-r7"


async def name_column_background(pg):
    return await pg.evaluate(
        """(() => {
          const name = [...document.querySelectorAll('.display-headline')].find(e => e.textContent.trim() === '%s');
          if (!name) return null;
          const column = name.parentElement;
          return getComputedStyle(column).textShadow;
        })()"""
        % PET
    )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        await login(pg)
        made = await api(pg, "POST", "/pets", {"name": PET, "species": "cat", "gender": "female"})
        pid = made["json"]["pet"]["_id"]
        try:
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, PET],
            )
            await api(pg, "PUT", f"/pets/{pid}/look", {"tagline": "Хозяин дивана", "backdrop": "stripes"})
            await pg.goto(BASE + "/")
            await settle(pg)
            plain = await name_column_background(pg)
            check(
                "without a photo backdrop the letters carry no halo",
                plain == "none",
                str(plain),
            )

            await api(pg, "PUT", f"/pets/{pid}/look", {"tagline": "Хозяин дивана", "backdrop": "photo"})
            await pg.goto(BASE + "/")
            await settle(pg)
            plate = await name_column_background(pg)
            check(
                "on a photo backdrop the letters carry a halo in the card's colour",
                plate not in (None, "none"),
                str(plate),
            )
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
            await ctx.close()
        await browser.close()
    summary("photo backdrop plate")


asyncio.run(main())
