"""A visit keeps the weighing said at it: its row shows that weight and opens that very weighing.

The weight said at a new visit goes to the diary; the visit points at it. Another weighing the same day must not be taken
for the visit's own, and the row opens the weighing itself, not the history.

Needs the local stand and the demo data. Makes a scratch pet «Тест-М» of its own and removes it.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, settle, summary
from scratch import drop_pet, make_pet


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        pid = await make_pet(pg)
        try:
            await pg.goto(f"{BASE}/pets/{pid}/medical-records/new?kind=visit")
            await settle(pg)
            await pg.get_by_text("Повод визита").first.click()
            await pg.wait_for_function(
                "() => document.activeElement && document.activeElement.tagName === 'INPUT'", timeout=8000
            )
            await pg.keyboard.type("Плановый осмотр")
            row = pg.locator(".prodpick__row", has_text="Плановый осмотр").first
            await row.wait_for(timeout=8000)
            await row.click()
            await row.wait_for(state="hidden", timeout=8000)
            await pg.get_by_label("Вес (кг)").fill("6,6")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await settle(pg, 400)

            rows = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
            visit = next((r for r in rows if r["kind"] == "visit"), None)
            check("the visit is saved", visit is not None, str(len(rows)))
            weighed = (await api(pg, "GET", f"/events?pet_id={pid}&type=weight"))["json"]
            events = weighed.get("items") or weighed.get("events") or []
            check("the weighing is in the diary", len(events) == 1, str(len(events)))
            check(
                "the visit points at that weighing",
                bool(visit) and len(events) == 1 and visit.get("weight_event_id") == events[0]["_id"],
                str(visit and visit.get("weight_event_id")),
            )

            # another weighing the same day, later: it must not be shown as the visit's
            await api(
                pg,
                "POST",
                "/events",
                {
                    "pet_id": pid,
                    "type": "weight",
                    "date": visit["date"],
                    "time": "23:30",
                    "fields": {"weight": 9.9},
                    "comment": "",
                    "tz": "Asia/Almaty",
                },
            )
            await pg.goto(f"{BASE}/pets/{pid}/medical-records/{visit['_id']}")
            await settle(pg, 300)
            body = await pg.inner_text("body")
            check(
                "the row shows the visit's own weight",
                "6,6 кг" in body and "9,9" not in body,
                body[-260:].replace("\n", " | "),
            )
            await pg.get_by_text("Вес в этот день").click()
            await settle(pg, 300)
            check(
                "and opens that weighing, not the history",
                f"/form/weight/{events[0]['_id']}" in pg.url,
                pg.url.replace(BASE, ""),
            )

            await pg.goto(f"{BASE}/pets/{pid}/medical-records/{visit['_id']}")
            await settle(pg, 300)
            await pg.get_by_role("button", name="Сохранить", exact=True).click()
            await settle(pg, 400)
            rows = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
            kept = next((r for r in rows if r["kind"] == "visit"), {})
            check(
                "an edit of the visit keeps the link",
                kept.get("weight_event_id") == events[0]["_id"],
                str(kept.get("weight_event_id")),
            )
        finally:
            await drop_pet(pg, pid)
            await b.close()
    return summary("вес визита привязан к визиту")


asyncio.run(main())
