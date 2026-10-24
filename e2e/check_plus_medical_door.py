"""The round «+» of the feed has a door to the medical records: a vaccination, a treatment, a visit.

Those records live on the medical card behind a second «+»; the diary's window is where a person looks first. The door leads
to the chooser of the record kinds of the chosen pet.

Needs the local stand and the demo data. Only opens screens; nothing is written.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, settle, summary


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        pid = await login(pg, "demo", "Рекс")
        await pg.goto(BASE + "/")
        await settle(pg)
        await pg.locator(".app-fab").click()
        door = pg.get_by_role("button", name="Прививка, визит или обработка")
        await door.wait_for(state="visible", timeout=10000)
        check("the window of «+» has a door to the medical records", await door.count() == 1)
        await door.click()
        await settle(pg, 300)
        check(
            "it leads to the chooser of the record kinds of this pet",
            pg.url.endswith(f"/pets/{pid}/medical-records/new"),
            pg.url.replace(BASE, ""),
        )
        body = await pg.inner_text("body")
        check(
            "and the chooser offers a vaccination and a visit",
            "Прививка" in body and "Визит" in body,
            body[:200].replace("\n", " | "),
        )
        await b.close()
    return summary("«+» ленты: вход в прививку, визит, обработку")


asyncio.run(main())
