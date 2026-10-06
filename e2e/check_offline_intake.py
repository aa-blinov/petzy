"""A mark the server already has must be said, not swallowed.

A dose marked with no connection is kept on the phone and sent later. If the
first attempt did get through and only its answer was lost, the server answers
409 when the mark is retried. The mark was dropped from the queue silently:
the person never learned their dose is in the diary, and the notice «Не
отправлено» simply disappeared.

Needs the local stack. Uses the demo pet Рекс with a course of its own and
removes it afterwards.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

PENDING_KEY = "petzy:pendingIntakes"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        medication_id = None
        try:
            created = await api(
                pg,
                "POST",
                "/medications",
                {
                    "pet_id": rex,
                    "name": "Т-проверка 409",
                    "type": "Таблетка",
                    "default_dose": 1,
                    "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["09:00"]},
                },
            )
            medication_id = created["json"]["id"]
            # The dose the queue will claim to send is already in the diary.
            taken = await api(
                pg,
                "POST",
                f"/medications/{medication_id}/log",
                {"date": "2026-10-01", "time": "09:00", "dose_taken": 1},
            )
            check("the dose is on the server to begin with", taken["status"] in (200, 201), str(taken["status"]))

            await pg.goto(BASE + "/medications")
            await pg.wait_for_timeout(1500)
            # The phone kept the mark whose answer was lost: same dose, one
            # moment earlier, so the server sees it as the same slot.
            await pg.evaluate(
                """([key, item]) => localStorage.setItem(key, JSON.stringify([{
                    key: 'e2e-409', medicationId: item.id, name: item.name,
                    input: {date: item.date, time: item.time, dose_taken: 1},
                }]))""",
                [PENDING_KEY, {"id": medication_id, "name": "Т-проверка 409", "date": "2026-10-01", "time": "09:00"}],
            )
            await pg.reload()
            # App.tsx sends what is waiting as soon as it sees it.
            await pg.wait_for_timeout(3000)
            body = await pg.inner_text("body")
            check(
                "the person is told the dose is already in the diary",
                "уже есть в журнале" in body,
                body[:200].replace(chr(10), " | "),
            )
            check(
                "and it is not said as a failure",
                "не удалось отправить" not in body,
                body[:200].replace(chr(10), " | "),
            )
            check(
                "the mark leaves the queue, so it is not sent again",
                await pg.evaluate(f"JSON.parse(localStorage.getItem('{PENDING_KEY}') || '[]').length") == 0,
            )
            listed = await api(pg, "GET", f"/medications/intakes?pet_id={rex}&page_size=50")
            mine = [r for r in listed["json"]["intakes"] if r.get("medication_id") == medication_id]
            check(
                "and nothing is written twice",
                len(mine) == 1,
                str([r.get("date_time") for r in mine]),
            )
        finally:
            if medication_id:
                await api(pg, "DELETE", f"/medications/{medication_id}")
        await b.close()
    summary("offline intake 409")


asyncio.run(main())
