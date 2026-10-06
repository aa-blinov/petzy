"""Every preparation is one dropdown with a search: a vaccine, a treatment, a medicine. A change of brand keeps one line on the card."""

import asyncio
import re
import time

from common import BASE, api, async_playwright, check, login, new_page, summary, swipe_wheel, wait_until


async def nav(pg, path, ready=None):
    """Go by history, the way the app itself does, and wait for the screen that opens.

    A flat pause here was a guess in both directions: too short read a slow screen as an
    empty one, and thirty of them were most of this check's time.
    """
    await pg.evaluate("p => { history.pushState({}, '', p); dispatchEvent(new PopStateEvent('popstate')) }", path)
    if ready:
        await wait_until(pg, lambda text: ready in text)
    else:
        await pg.wait_for_timeout(400)


async def rows_with(pg, text, timeout=8000):
    """The picker rows as soon as one of them carries the word, not after a pause."""
    deadline = time.monotonic() + timeout / 1000
    rows = await pg.locator(".prodpick__row").all_inner_texts()
    while time.monotonic() < deadline and not any(text in row for row in rows):
        await pg.wait_for_timeout(150)
        rows = await pg.locator(".prodpick__row").all_inner_texts()
    return rows


async def saved(pg):
    """Wait for the save to land: the form gives way to the card it came from."""
    await pg.wait_for_url(lambda url: "medical-records/new" not in url and "medications/new" not in url, timeout=15000)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        await pg.goto(BASE + "/pets/new")
        await pg.get_by_role("button", name="Собака").click()
        await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
        await pg.get_by_role("button", name="Добавить", exact=True).click()
        await pg.get_by_role("button", name="Готово").click()
        await pg.wait_for_timeout(300)
        pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
        card = f"/pets/{pid}/medical-card"
        try:
            old = (
                await api(
                    pg,
                    "POST",
                    "/medical-records",
                    {
                        "pet_id": pid,
                        "kind": "vaccination",
                        "date": "2025-06-01",
                        "title": "Нобивак DHPPi",
                        "next_due": "2026-06-01",
                    },
                )
            )["json"]["id"]
            # ---- a vaccine: a row, a search, no chips
            await pg.goto(BASE + card)
            await nav(pg, f"/pets/{pid}/medical-records/new?kind=vaccination", "Название вакцины")
            body = await pg.inner_text("body")
            check(
                "the vaccine is a row, with no cloud of chips under it",
                await pg.get_by_role("group", name="Подсказки").count() == 0 and "Выберите или впишите" in body,
            )
            check(
                "no «Найти в списке» button and no extra vaccinations of the day",
                "Найти в списке" not in body and "Ещё прививки в этот день" not in body,
            )
            await pg.get_by_text("Название вакцины").first.click()
            # Фокус в поиске приходит позже заголовков групп, а без него напечатанное уходит
            # в никуда: ждём именно его, а не «лист уже нарисован».
            await pg.wait_for_function(
                "() => document.activeElement && document.activeElement.tagName === 'INPUT'",
                timeout=8000,
            )
            check(
                "the sheet opens with the earlier name first",
                await pg.locator(".prodpick__group-title").first.inner_text() == "Ранее у питомца",
            )
            check(
                "the cursor is in the search",
                await pg.evaluate("document.activeElement && document.activeElement.tagName") == "INPUT",
            )
            await pg.keyboard.type("эурикан")
            rows = await rows_with(pg, "Эурикан DHPPi2")
            check(
                "typing filters the list",
                any("Эурикан DHPPi2" in r for r in rows) and not any("Rabies" in r for r in rows),
                str(rows),
            )
            await pg.locator(".prodpick__row", has_text=re.compile("^Эурикан DHPPi2$")).click()
            body = await wait_until(pg, lambda t: "От чего" in t and "Комплексная для собак" in t)
            check("the name is in the row", "Эурикан DHPPi2" in body)
            check(
                "«От чего» is a dropdown row and says Комплексная для собак",
                "От чего" in body
                and "Комплексная для собак" in body
                and await pg.get_by_role("group", name="От чего защищает прививка").count() == 0,
            )
            check("and that it replaces the old entry", "Заменит «Нобивак DHPPi»" in body)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await saved(pg)
            rows = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
            by = {x["_id"]: x for x in rows}
            check(
                "the old brand is history, the new one keeps its protection",
                by[old]["superseded"] and any(x["protects"] == "dhpp" and x["_id"] != old for x in rows),
            )
            # ---- a typed vaccine and a hand choice of the protection from the dropdown
            await pg.goto(BASE + card)
            await nav(pg, f"/pets/{pid}/medical-records/new?kind=vaccination", "Название вакцины")
            await pg.get_by_text("Название вакцины").first.click()
            await pg.wait_for_function(
                "() => document.activeElement && document.activeElement.tagName === 'INPUT'",
                timeout=8000,
            )
            await pg.keyboard.type("Своя вакцина")
            # Строка «своё» появляется только после набора: до него её на листе нет.
            await pg.locator(".prodpick__row--own").wait_for(timeout=8000)
            await pg.locator(".prodpick__row--own").click()
            # Ждём, пока лист закроется: написанное имя и на листе видно, так что «видно имя»
            # не значит «лист закрылся», а «От чего» под открытым листом не нажимается.
            await pg.locator(".prodpick__row--own").wait_for(state="hidden", timeout=8000)
            check("a typed name is used as typed", "Своя вакцина" in await pg.inner_text("body"))
            await pg.get_by_text("От чего").first.click()
            # Палец по колесу бьёт по координатам, взятым у него сейчас, поэтому колесо должно
            # не просто появиться, а встать на место: лист с ним подъезжает снизу.
            await pg.wait_for_timeout(700)
            await swipe_wheel(pg, ctx, 0, 1)
            await pg.locator(".adm-picker-header-button", has_text="Готово").last.click()
            # Колесо должно закрыться и отдать выбор форме, иначе «Добавить» уходит раньше.
            await pg.locator(".adm-picker-view-column-wheel").first.wait_for(state="hidden", timeout=8000)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await saved(pg)
            rows = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
            check(
                "saved with the protection chosen in the dropdown",
                any(x["title"] == "Своя вакцина" and x["protects"] == "rabies" for x in rows),
                str([(x["title"], x["protects"]) for x in rows]),
            )
            # ---- a treatment
            await pg.goto(BASE + card)
            await nav(pg, f"/pets/{pid}/medical-records/new?kind=parasite", "Препарат")
            body = await pg.inner_text("body")
            check(
                "the treatment is a row too, no chips",
                "Подсказки" not in body and await pg.get_by_role("group", name="Подсказки").count() == 0,
            )
            await pg.get_by_text("Препарат").first.click()
            await pg.locator(".prodpick__row").first.wait_for(timeout=8000)
            await pg.keyboard.type("брав")
            await rows_with(pg, "Бравекто")
            await pg.locator(".prodpick__row", has_text=re.compile("^Бравекто$")).click()
            body = await wait_until(pg, lambda t: "Блохи и клещи" in t)
            check("a listed product puts «Блохи и клещи» in", "Блохи и клещи" in body)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await saved(pg)
            rows = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
            check(
                "it saves with its target", any(x["title"] == "Бравекто" and x["target"] == "fleas_ticks" for x in rows)
            )
            # ---- a treatment typed by hand needs its target
            await pg.goto(BASE + card)
            await nav(pg, f"/pets/{pid}/medical-records/new?kind=parasite", "Препарат")
            await pg.get_by_text("Препарат").first.click()
            await pg.wait_for_function(
                "() => document.activeElement && document.activeElement.tagName === 'INPUT'",
                timeout=8000,
            )
            await pg.keyboard.type("Что-то своё")
            await pg.keyboard.press("Enter")
            await wait_until(pg, lambda t: "Что-то своё" in t and "Препарат" in t)
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            body = await wait_until(pg, lambda t: "Укажите, от чего обработка" in t)
            check(
                "a typed treatment without «От чего» is not saved and says so",
                "Укажите, от чего обработка" in body and "medical-records/new" in pg.url,
            )
            # ---- a medicine
            await pg.goto(BASE + "/medications")
            await nav(pg, "/medications/new", "Название")
            body = await pg.inner_text("body")
            check("the medicine form has no separate «частые лекарства» button", "частых лекарств" not in body)
            await pg.get_by_text("Название", exact=True).first.click()
            await pg.locator(".prodpick__group").nth(3).wait_for(timeout=8000)
            check(
                "the medicine list opens with a search and groups by purpose",
                await pg.locator(".prodpick__group").count() >= 4,
            )
            await pg.keyboard.type("мелок")
            await rows_with(pg, "Мелоксидил")
            await pg.locator(".prodpick__row", has_text=re.compile("^Мелоксидил$")).click()
            body = await wait_until(pg, lambda t: "Мелоксидил" in t and "Суспензия" in t)
            check(
                "a known medicine brings its form and strength",
                "Мелоксидил" in body
                and "Суспензия" in body
                and "0,5 мг/мл"
                in await pg.evaluate("[...document.querySelectorAll('input')].map(i => i.value).join('|')"),
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
            await pg.screenshot(path="pk_med.png")
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("one dropdown for every preparation")


asyncio.run(main())
