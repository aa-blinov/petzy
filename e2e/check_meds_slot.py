"""A slot of the schedule cannot be closed twice, and the question says so: the same 08:00 dose, marked by
another hand hours later, is asked about as the slot («Это время уже отмечено») instead of being written twice.

Also the second rule the same screen carries: a dose marked with no connection stays on its own card with
«Не отправлено» and its buttons wait, rather than only a line above the whole list.

Needs the local stack and the demo data. Makes three courses of its own and removes them."""

import asyncio
from datetime import datetime, timedelta

from common import BASE, api, async_playwright, check, login, new_page, summary

SLOTS = "Т-проверка слот"
QUESTION = "Т-проверка вопрос"
NEEDED = "Т-проверка по необходимости"


def course(name: str, times: list[str]) -> dict:
    schedule = {"days": [0, 1, 2, 3, 4, 5, 6], "times": times} if times else {"days": [], "times": []}
    return {
        "name": name,
        "type": "Таблетка",
        "default_dose": 1,
        "dose_unit": "таб",
        "schedule": schedule,
        "is_active": True,
    }


async def intakes(pg, pet_id: str, med_id: str) -> list[dict]:
    """The pet's intakes, narrowed to one course: the list endpoint is by pet, and it names the medicine."""
    return await pg.evaluate(
        """async ([pet, id]) => { const r = await fetch('/api/medications/intakes?pet_id=' + pet + '&page_size=100', {credentials: 'include'});
            const j = await r.json(); return (j.intakes || j.data || j.items || [])
                .filter(i => i.medication_id === id).map(i => i.slot_time); }""",
        [pet_id, med_id],
    )


async def main():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    # Two slots, an hour and two hours behind: a dose marked late is what a dose given by somebody
    # else looks like, and both slots are in the past so the sheet still offers the one left.
    first = now.replace(hour=max(0, now.hour - 2), minute=0, second=0, microsecond=0)
    later = now.replace(hour=max(0, now.hour - 1), minute=0, second=0, microsecond=0)
    if first == later:
        first = first - timedelta(hours=1)
    times = sorted([first.strftime("%H:%M"), later.strftime("%H:%M")])
    # The moment a second hand writes it, far from the first one: the old guard let this through.
    late = later.replace(minute=min(59, later.minute + 20)).strftime("%H:%M")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        ids = []
        try:
            for name, own_times in ((SLOTS, times), (QUESTION, times), (NEEDED, [])):
                r = await api(pg, "POST", "/medications", {**course(name, own_times), "pet_id": rex})
                ids.append(r["json"]["id"])
            slots, question, needed = ids

            await pg.goto(BASE + "/medications")
            await pg.wait_for_timeout(2500)

            # One slot is closed, the other is not.
            first_mark = await api(
                pg,
                "POST",
                f"/medications/{slots}/log",
                {"date": today, "time": times[0], "slot_date": today, "slot_time": times[0]},
            )
            check("the first mark of a slot is written", first_mark["status"] == 201, f"status {first_mark['status']}")

            # Another hand, on the same dose of the same day.
            clash = await api(
                pg,
                "POST",
                f"/medications/{slots}/log",
                {"date": today, "time": late, "slot_date": today, "slot_time": times[0]},
            )
            check(
                "a slot closed hours ago is refused, not written twice",
                clash["status"] == 409,
                f"status {clash['status']}",
            )
            body = clash["json"] or {}
            check(
                "the question is about the slot",
                body.get("existing", {}).get("slot") is True and "уже отмечен" in body.get("error", ""),
                str(body.get("error")),
            )
            other_slot_mark = await api(
                pg,
                "POST",
                f"/medications/{slots}/log",
                {"date": today, "time": late, "slot_date": today, "slot_time": times[1]},
            )
            check(
                "the other slot of the same course is written as usual",
                other_slot_mark["status"] == 201,
                f"status {other_slot_mark['status']}",
            )
            check(
                "two intakes are stored, no more",
                len(await intakes(pg, rex, slots)) == 2,
                str(await intakes(pg, rex, slots)),
            )

            # The same question through the screen, in the order it really happens: the sheet is open with the
            # slot it offers, and the other person takes it before the mark is written. A fresh list
            # never offers a closed slot, so this is the case a stale screen leaves.
            card = pg.locator(".card-soft", has_text=QUESTION).first
            await card.get_by_role("button", name="Другое время или доза").click()
            await pg.wait_for_timeout(1500)
            await api(
                pg,
                "POST",
                f"/medications/{question}/log",
                {"date": today, "time": late, "slot_date": today, "slot_time": times[0]},
            )
            await pg.get_by_role("button", name=f"В {times[0]}").click()
            await pg.wait_for_timeout(600)
            await pg.get_by_role("button", name="Записать", exact=True).click()
            await pg.wait_for_timeout(2000)
            screen = await pg.locator("body").inner_text()
            check(
                "the question in the app speaks of the time, not of a dose near in time",
                "Это время уже отмечено" in screen and f"приём на {times[0]}" in screen,
                screen.replace("\n", " | ")[:160],
            )
            check("the one who took the slot is named", "вами" in screen, screen.replace("\n", " | ")[:160])
            await pg.get_by_role("button", name="Не записывать").last.click()
            await pg.wait_for_timeout(1500)
            check(
                "the refused mark left the intakes as they were",
                len(await intakes(pg, rex, question)) == 1,
                str(await intakes(pg, rex, question)),
            )

            # A course with no schedule can always be given again, even in the same minute.
            await api(pg, "POST", f"/medications/{needed}/log", {"date": today, "time": late})
            again = await api(pg, "POST", f"/medications/{needed}/log", {"date": today, "time": late})
            check(
                "a course given when needed takes another dose at the same minute",
                again["status"] == 201,
                f"status {again['status']}",
            )

            # With no connection the mark cannot leave the phone: the card of its own course says so
            # and offers no second tap, instead of only a line above the whole list.
            await pg.goto(BASE + "/medications", wait_until="domcontentloaded")
            await pg.wait_for_timeout(2500)
            await ctx.set_offline(True)
            card = pg.locator(".card-soft", has_text=NEEDED).first
            await card.get_by_role("button", name="Дали сейчас").click()
            await pg.wait_for_timeout(2500)
            card = pg.locator(".card-soft", has_text=NEEDED).first
            text = await card.inner_text()
            check(
                "the card of the course says the mark is not sent",
                "не отправлен" in text,
                text.replace("\n", " | ")[:160],
            )
            button = card.get_by_role("button", name=f"{NEEDED}: приём отмечен, но не отправлен")
            check(
                "its button waits instead of offering a second mark",
                await button.count() == 1 and await button.is_disabled(),
            )
            check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
            await ctx.set_offline(False)
        finally:
            await pg.evaluate("localStorage.removeItem('petzy:pendingIntakes')")
            for i in ids:
                await api(pg, "DELETE", f"/medications/{i}")
        await b.close()
    summary("the slot of a dose")


asyncio.run(main())
