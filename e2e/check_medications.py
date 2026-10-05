"""The medicines list: a missed dose is said as missed and the next as next, a dose given late closes the dose that was due and not the
evening one, and two taps in one moment are one dose.

Needs the local stack and the demo data. Makes two courses of its own and removes them."""

import asyncio
from datetime import datetime

from common import BASE, api, async_playwright, check, login, new_page, summary


async def line(card) -> str:
    return await card.evaluate("e => e.innerText.split('\\n').filter(x => x.startsWith('Сегодня')).join(' | ')")


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


async def main():
    now = datetime.now().strftime("%H:%M")
    if not "00:05" < now < "23:55":
        print("SKIP the clock is at a day's edge: the slots of this check (00:01 and 23:59) would be on the wrong side")
        return
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        ids = []
        try:
            for name, times in (("Т-проверка два приёма", ["00:01", "23:59"]), ("Т-проверка по необходимости", [])):
                r = await api(pg, "POST", "/medications", {**course(name, times), "pet_id": rex})
                ids.append(r["json"]["id"])
            await pg.goto(BASE + "/medications")
            await pg.wait_for_timeout(2500)
            two = pg.locator(".card-soft", has_text="Т-проверка два приёма").first
            check(
                "a missed dose is said as missed, the next as next",
                await line(two) == "Сегодня 0 из 2, не отмечено в 00:01, дальше в 23:59",
                await line(two),
            )
            await two.get_by_role("button", name="Дали сейчас").click()
            await pg.wait_for_timeout(2000)
            two = pg.locator(".card-soft", has_text="Т-проверка два приёма").first
            check(
                "a dose given late closes the dose that was due, the evening one stays",
                await line(two) == "Сегодня 1 из 2, дальше в 23:59",
                await line(two),
            )
            needed = pg.locator(".card-soft", has_text="Т-проверка по необходимости").first
            await needed.get_by_role("button", name="Дали сейчас").dblclick()
            await pg.wait_for_timeout(1800)
            needed = pg.locator(".card-soft", has_text="Т-проверка по необходимости").first
            text = await needed.inner_text()
            check(
                "two taps in one moment write one dose",
                "Сегодня давали: 1 раз" in text,
                text.replace("\n", " | ")[:160],
            )
            check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        finally:
            for i in ids:
                await api(pg, "DELETE", f"/medications/{i}")
        await b.close()
    summary("the medicines list")


asyncio.run(main())
