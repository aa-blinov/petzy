"""«По необходимости» is a sign of its own: the course keeps its days and times, the mode comes
back from the stored sign, and nothing is due or reminded about.

Needs the local stack and the demo data. Makes a course of its own and removes it."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

COURSE = "Т-проверка по необходимости"


async def days_text(pg) -> int:
    return await pg.evaluate(
        """() => [...document.querySelectorAll('.selector-chips .adm-selector-item')]
            .filter(e => e.className.includes('multiple-active')).length"""
    )


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        med = None
        try:
            r = await api(
                pg,
                "POST",
                "/medications",
                {
                    "pet_id": rex,
                    "name": COURSE,
                    "type": "Таблетка",
                    "default_dose": 1,
                    "dose_unit": "таб",
                    "schedule": {"days": [1, 3, 5], "times": ["09:00", "21:00"]},
                    "as_needed": False,
                    "is_active": True,
                },
            )
            med = r["json"]["id"]

            # Switch the mode in the form and save: the schedule comes with it.
            await pg.goto(BASE + f"/medications/{med}/edit")
            await pg.wait_for_timeout(2500)
            before = await days_text(pg)
            await pg.locator(".segmented__item", has_text="По необходимости").click()
            await pg.wait_for_timeout(1000)
            await pg.get_by_role("button", name="Сохранить").click()
            await pg.wait_for_timeout(2500)

            stored = (await api(pg, "GET", f"/medications/{med}"))["json"]["medication"]
            check(
                "the mode is stored as the sign, not read out of an empty schedule",
                stored.get("as_needed") is True,
                str(stored.get("as_needed")),
            )
            check(
                "a course «по необходимости» keeps its days and times",
                stored["schedule"]["times"] == ["09:00", "21:00"] and stored["schedule"]["days"] == [1, 3, 5],
                str(stored["schedule"]),
            )

            # And it is not due today, though it has a schedule.
            listing = (await api(pg, "GET", f"/medications?pet_id={rex}"))["json"]["medications"]
            mine = next(m for m in listing if m["_id"] == med)
            check(
                "a course «по необходимости» is not due today",
                mine.get("scheduled_today") is False,
                str(mine.get("scheduled_today")),
            )

            upcoming = (await api(pg, "GET", f"/medications/upcoming?pet_id={rex}"))["json"]
            check(
                "and it is not among the doses to come",
                all(d.get("medication_id") != med for d in upcoming.get("doses", [])),
                str([d.get("medication_id") for d in upcoming.get("doses", [])]),
            )

            # The form reads the sign back: it opens in «по необходимости» with the week still in it.
            await pg.goto(BASE + f"/medications/{med}/edit")
            await pg.wait_for_timeout(2500)
            check(
                "the form opens in «по необходимости», the stored sign and not the empty schedule",
                "Без напоминаний" in await pg.locator("body").inner_text(),
            )
            await pg.locator(".segmented__item", has_text="По расписанию").click()
            await pg.wait_for_timeout(1000)
            after = await days_text(pg)
            check(
                "the days and times came back with the mode",
                after == before,
                f"{before} days before, {after} after",
            )
            check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        finally:
            if med:
                await api(pg, "DELETE", f"/medications/{med}")
        await b.close()
    summary("«по необходимости» as a sign")


asyncio.run(main())
