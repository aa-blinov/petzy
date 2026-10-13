"""The owner can put an overdue repeat right from the strip on the vet's copy too.

A person who owns the pet sees «Врачу» with the same overdue strip as «Записи». The strip used to offer the
link only in the working copy, and on the vet's copy told the owner «Открыть раздел и обновить сможет владелец»,
which is not true for the owner. The link must be there on both copies. A throwaway pet with an overdue vaccine
is made for the check and deleted afterwards.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

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
            await pg.wait_for_timeout(1500)
            await pg.get_by_role("button", name="Врачу").first.click()
            await pg.wait_for_timeout(800)
            on_vet_copy = await pg.get_by_text(LINK).count()
            check("owner sees the repeat link on the vet's copy", on_vet_copy > 0)
            check(
                "owner is not told that only the owner can update it",
                await pg.get_by_text("обновить сможет владелец").count() == 0,
            )

            await pg.get_by_role("button", name="Записи").first.click()
            await pg.wait_for_timeout(800)
            check("owner still sees the link in the working copy", await pg.get_by_text(LINK).count() > 0)
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await ctx.close()
        await browser.close()
    summary("medcard owner strip")


asyncio.run(main())
