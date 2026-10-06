"""The medicine form says where a name is typed, and the schedule survives a look at «по необходимости»:
the days and times a course was written with stay in the form while the mode flips, so a question about
the mode does not cost the week's days.

Needs the local stack and the demo data. Makes a course of its own and removes it."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

COURSE = "Т-проверка расписание"


async def days_text(pg) -> str:
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
                    "is_active": True,
                },
            )
            med = r["json"]["id"]

            await pg.goto(BASE + f"/medications/{med}/edit")
            await pg.wait_for_timeout(2500)

            # Where a name is typed is said on the row, so the sheet is not a dead end.
            await pg.get_by_text("Название", exact=True).first.click()
            await pg.wait_for_timeout(1500)
            search = pg.get_by_role("searchbox").first
            await search.fill("Т-несуществующее")
            await pg.wait_for_timeout(1200)
            check(
                "a name that is not in the list can still be taken from the search",
                await pg.get_by_text("Использовать «Т-несуществующее»").count() == 1,
            )
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(800)

            # The hint under the name row is what says so.
            check(
                "the name row says the name is typed in the search",
                "впишите название в поиске" in (await pg.locator("body").inner_text()).lower(),
            )

            before = await days_text(pg)
            check("the course's days are on the form to begin with", before == 3, f"{before} days")

            await pg.locator(".segmented__item", has_text="По необходимости").click()
            await pg.wait_for_timeout(1200)
            check(
                "the mode is written as a sign of its own, not an empty schedule",
                "Без напоминаний" in await pg.locator("body").inner_text(),
            )
            await pg.locator(".segmented__item", has_text="По расписанию").click()
            await pg.wait_for_timeout(1200)
            after = await days_text(pg)
            check(
                "the days a course was written with come back with the mode",
                after == before,
                f"{before} days before, {after} after",
            )
            check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        finally:
            if med:
                await api(pg, "DELETE", f"/medications/{med}")
        await b.close()
    summary("the schedule of a medicine")


asyncio.run(main())
