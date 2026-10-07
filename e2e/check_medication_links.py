"""A course of another pet is opened under that pet, and an address with no screen says so.

Two screens that used to lie about what happened:

1. `/medications/<id>/edit` looked for the course in the chosen pet's list, and a course of
   another pet is not in it. The answer was «Такого лекарства нет, его удалили или он не открыт
   вашему питомцу» while the course was there and access to it was fine. Now the course is asked
   for by its own address (the server answers 404 only when it is really gone), and the pet it
   belongs to becomes the chosen one, as it does on the medical card. Otherwise the form would
   show the wrong pet and save the course under it.

2. Any address without a screen answered with a jump to the feed: an old link, a typo, a cut-off
   address. The person landed on the feed with nothing saying the address was wrong.

Needs the local stack and the demo data. Makes a pet and a course of its own and removes both.
"""

import asyncio
import json

from common import BASE, api, async_playwright, check, login, new_page, summary

OTHER_PET = "Тест-К"
COURSE = "Т-проверка курс чужого питомца"


async def selected_pet(pg) -> str | None:
    """The chosen pet's id. localStorage keeps it as JSON, so `"6ac…"` comes back with quotes."""
    raw = await pg.evaluate("() => localStorage.getItem('selectedPetId')")
    return json.loads(raw) if raw else None


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        other = course_id = None
        try:
            for leftover in (await api(pg, "GET", "/pets"))["json"]["pets"]:
                if leftover["name"] == OTHER_PET:
                    await api(pg, "DELETE", f"/pets/{leftover['_id']}")
            other = (await api(pg, "POST", "/pets", {"name": OTHER_PET, "species": "собака"}))["json"]["pet"]["_id"]
            made = await api(
                pg,
                "POST",
                "/medications",
                {
                    "pet_id": other,
                    "name": COURSE,
                    "type": "Таблетка",
                    "default_dose": 1,
                    "dose_unit": "таб",
                    "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["09:00"]},
                    "is_active": True,
                },
            )
            course_id = made["json"]["id"]

            # The chosen pet is the one the session opens with, and the course belongs to another.
            check(
                "проверка начинается с чужого питомца",
                (await selected_pet(pg)) == rex and rex != other,
                f"выбран {await selected_pet(pg)}, курс у {other}",
            )

            await pg.goto(BASE + f"/medications/{course_id}/edit")
            await pg.wait_for_timeout(2500)
            body = await pg.inner_text("body")
            check(
                "курс чужого питомца открывается, а не говорит, что его нет",
                "Такого лекарства нет" not in body and COURSE in body,
                body.replace("\n", " | ")[:110],
            )
            check(
                "и открывается под тем питомцем, которому он принадлежит",
                OTHER_PET in body,
                body.replace("\n", " | ")[:110],
            )
            chosen = await selected_pet(pg)
            check(
                "этот питомец становится выбранным",
                chosen == other,
                f"выбран {chosen}, курс у {other}",
            )

            # An address the app has no screen for says so instead of quietly becoming the feed.
            await pg.goto(BASE + "/medications/" + course_id)
            await pg.wait_for_timeout(1200)
            unknown = await pg.inner_text("body")
            check(
                "адрес без экрана говорит об этом",
                "Такого адреса нет" in unknown and "Лента" not in unknown.split("Такого адреса нет")[0][-40:],
                unknown.replace("\n", " | ")[:110],
            )
        finally:
            if course_id:
                await api(pg, "DELETE", f"/medications/{course_id}")
            if other:
                await api(pg, "DELETE", f"/pets/{other}")
        await b.close()

    summary("курс другого питомца и неизвестный адрес")


asyncio.run(main())
