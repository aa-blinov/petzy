"""Deleting a pet from its edit form, opened by its address, can still be taken back.

Same cause as the record form: «back» out of a page opened by its address unloads it, and the page's exit sent the
DELETE at once with no «Отменить». The form now leaves in the app, so the pet stays on the server while the bar is up.
A throwaway pet is made for the check and removed on «Отменить» or at the end.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

PET = "qa-petdel-direct"


async def pet_exists(pg, pid):
    return (await api(pg, "GET", f"/pets/{pid}"))["status"] == 200


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        await login(pg)
        pid = (await api(pg, "POST", "/pets", {"name": PET, "species": "dog", "gender": "male"}))["json"]["pet"]["_id"]
        try:
            await pg.goto(f"{BASE}/pets/{pid}/edit")
            await pg.wait_for_timeout(2000)
            await pg.get_by_role("button", name="Удалить питомца").first.click()
            await pg.locator(".adm-dialog-button", has_text="Удалить").last.click()
            await pg.wait_for_timeout(1500)

            check("the undo bar is shown", await pg.get_by_text("Отменить").count() > 0)
            check("the pet is still on the server while the bar is up", await pet_exists(pg, pid))

            await pg.get_by_text("Отменить").first.click()
            await pg.wait_for_timeout(1000)
            check("«Отменить» keeps the pet", await pet_exists(pg, pid))
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await ctx.close()
        await browser.close()
    summary("pet delete undo, direct address")


asyncio.run(main())
