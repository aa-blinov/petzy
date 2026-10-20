"""The owner can put an overdue repeat right from the block of what asks to be done.

The card is one document now: the same block of what is overdue stands on the owner's copy and
on the copy a vet opens by a link. The link is there for the owner, and it opens the form of
the repeat with that record as its base. A throwaway pet with an overdue vaccine is made for
the check and deleted afterwards.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle

PET = "qa-strip-owner"
LINK = "Записать повторную прививку"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        await login(pg)
        made = await api(pg, "POST", "/pets", {"name": PET, "species": "dog", "gender": "male"})
        pid = made["json"]["pet"]["_id"]
        try:
            record = await api(
                pg,
                "POST",
                "/medical-records",
                {
                    "pet_id": pid,
                    "kind": "vaccination",
                    "date": "2024-03-01",
                    "title": "Нобивак DHPPi",
                    "protects": "dhpp",
                    "next_due": "2025-03-01",
                },
            )
            check("throwaway pet has an overdue vaccine", record["status"] == 201, str(record["status"]))

            await pg.goto(f"{BASE}/pets/{pid}/medical-card")
            await settle(pg)
            zone = pg.locator(".medcard__attention")
            check("the card says what is overdue", await zone.count() == 1, (await pg.inner_text("body"))[:120])
            check(
                "the owner sees the repeat link",
                await zone.get_by_text(LINK).count() == 1,
                (await zone.inner_text()).replace(chr(10), " | "),
            )
            check(
                "the owner is not told that only the owner can update it",
                await pg.get_by_text("обновить сможет владелец").count() == 0,
            )
            await zone.get_by_text(LINK).click()
            await settle(pg, 150)
            check(
                "the link opens the form of the repeat with that record as its base",
                "kind=vaccination" in pg.url and "from=" in pg.url,
                pg.url.replace(BASE, ""),
            )
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await ctx.close()
        await browser.close()
    summary("medcard owner strip")


asyncio.run(main())
