"""The feed: a record that arrives while the next page is read is not drawn twice, the round plus steps aside on a scroll down, and an empty
block of medicine notices leaves no gap.

Needs the local stack and the demo data (docker compose -p petzy-local ... up, scripts/seed_demo.py). Makes three feedings of its own and removes them."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        received: list[str] = []

        async def on_response(r):
            if "/history/timeline" in r.url and r.status == 200:
                try:
                    received.extend(i["_id"] for i in (await r.json())["items"])
                except Exception:  # a response the page dropped
                    pass

        pg.on("response", lambda r: asyncio.ensure_future(on_response(r)))
        made = []
        made_pets = []
        try:
            await pg.goto(BASE + "/")
            await settle(pg)
            check("the feed has its h1", await pg.locator("h1").all_inner_texts() == ["Лента"])
            # The block is empty only when nothing is due: the demo pet has a dose at a clock time, so the check
            # uses a pet of its own with no medicines, and goes back to the demo pet afterwards.
            empty = await api(pg, "POST", "/pets", {"name": "qa-feed-empty", "species": "собака"})
            empty_id = empty["json"]["pet"]["_id"]
            made_pets.append(empty_id)
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [empty_id, "qa-feed-empty"],
            )
            await pg.goto(BASE + "/")
            await settle(pg)
            check(
                "an empty block of notices takes no room",
                await pg.evaluate("getComputedStyle(document.querySelector('.feed-widgets')).display") == "none",
            )
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [rex, "Рекс"],
            )
            await pg.goto(BASE + "/")
            await settle(pg)
            # three records arrive while page one is being read: the offsets of the next page move by three
            for i in range(3):
                r = await api(
                    pg,
                    "POST",
                    "/events",
                    {
                        "pet_id": rex,
                        "type": "feeding",
                        "date": "2026-10-05",
                        "time": f"15:{50 + i}",
                        "fields": {"food_weight": 100 + i},
                        "tz": "Asia/Almaty",
                    },
                )
                made.append(r["json"].get("id"))
            for _ in range(4):
                await pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await pg.wait_for_timeout(2000)
            cards = await pg.locator("[aria-label$=', открыть']").count()
            check(
                "the page the server repeated shows each record once",
                cards == len(set(received)) and len(received) > len(set(received)),
                f"{len(received)} received, {len(set(received))} unique, {cards} cards",
            )
            check("the round plus steps aside while reading down", await pg.locator(".app-fab--away").count() == 1)
            await pg.evaluate("window.scrollBy(0, -300)")
            await pg.wait_for_timeout(500)
            check("and comes back on a scroll up", await pg.locator(".app-fab--away").count() == 0)
            check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        finally:
            for pid in made_pets:
                await api(pg, "DELETE", f"/pets/{pid}")
            for m in made:
                if m:
                    await api(pg, "DELETE", f"/events/{m}")
        await b.close()
    summary("the feed")


asyncio.run(main())
