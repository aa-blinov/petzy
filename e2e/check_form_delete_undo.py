"""Deleting a record from its form, opened by its address, can still be taken back.

A form opened straight from an address has a previous page of another document. Leaving it by «back» unloaded
the page, and the page's exit sent the DELETE at once, with no «Отменить» left to offer. The form now leaves in
the app, so the record stays on the server while the bar is up and comes back on «Отменить». A throwaway pet and
its weight record are made for the check and removed afterwards.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle

PET = "qa-formdel-owner"


async def record_exists(pg, record_id):
    answer = await api(pg, "GET", f"/events/{record_id}")
    return answer["status"] == 200


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        await login(pg)
        pid = (await api(pg, "POST", "/pets", {"name": PET, "species": "dog", "gender": "male"}))["json"]["pet"]["_id"]
        try:
            made = await api(
                pg,
                "POST",
                f"/events?pet_id={pid}",
                {
                    "pet_id": pid,
                    "type": "weight",
                    "date": "2026-10-01",
                    "time": "09:00",
                    "fields": {"weight": 12},
                    "tz": "Asia/Almaty",
                },
            )
            check("throwaway weight record made", made["status"] == 201, str(made["status"]))
            record_id = made["json"]["id"]

            # Opened by its address: this page is the first of the session, so «back» leaves the app.
            await pg.goto(f"{BASE}/form/weight/{record_id}")
            await settle(pg)
            await pg.get_by_role("button", name="Удалить запись").first.click()
            await settle(pg, 150)

            check("the undo bar is shown", await pg.get_by_text("Запись удалена").count() > 0)
            check("«Отменить» is offered", await pg.get_by_text("Отменить").count() > 0)
            check(
                "the record is still on the server while the bar is up",
                await record_exists(pg, record_id),
            )

            await pg.get_by_text("Отменить").first.click()
            await settle(pg, 150)
            check("«Отменить» keeps the record", await record_exists(pg, record_id))
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await ctx.close()
        await browser.close()
    summary("form delete undo")


asyncio.run(main())
