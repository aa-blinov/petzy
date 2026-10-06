"""The History screen: the filter lives in the address, the chart says what it shows, the export button is named, and the record form names the pet and who wrote the record.

Needs the local stack. Makes its own pet «Тест-М» with three weights of its own and removes it."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

PET = "Тест-М"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        made = await api(pg, "POST", "/pets", {"name": PET, "species": "dog", "gender": "male"})
        pid = made["json"]["pet"]["_id"]
        try:
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id));"
                " localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, PET],
            )
            # Three weights inside the last month, so the trend chart has a first, a last and a change.
            for day, weight in ((1, 12.0), (10, 12.4), (20, 12.6)):
                r = await api(
                    pg,
                    "POST",
                    "/events",
                    {
                        "pet_id": pid,
                        "type": "weight",
                        "date": f"2026-09-{day:02d}",
                        "time": "09:00",
                        "fields": {"weight": weight},
                    },
                )
                check(f"weight of {weight} is on the server", r["status"] in (200, 201), str(r["status"]))

            # The filter comes in the address from the start and stays there.
            await pg.goto(BASE + "/history?type=weight")
            await pg.wait_for_timeout(2500)
            check(
                "a filtered screen is the one the address names",
                pg.url.endswith("/history?type=weight"),
                pg.url.replace(BASE, ""),
            )

            # The chart in words: a first, a last, a change, and the unit beside every value.
            summary_line = await pg.evaluate(
                """() => { const ps = [...document.querySelectorAll('p')];
                   return ps.map(p => p.textContent.trim()).find(t => t.startsWith('За месяц:')) || ''; }"""
            )
            check(
                "the chart says its first and last reading with the unit, in one line of its own",
                "За месяц:" in summary_line and "12,4 кг" in summary_line and "12,6 кг" in summary_line,
                summary_line,
            )
            check("and says how much it moved", "плюс 0,2 кг" in summary_line, summary_line)

            # Changing the filter writes it back to the address, and reloading keeps it.
            await pg.get_by_role("button", name="Показать записи", exact=False).count()
            await pg.locator(".history-filter-trigger").click()
            await pg.wait_for_timeout(700)
            await pg.get_by_role("button", name="Все", exact=True).first.click()
            await pg.wait_for_timeout(1800)
            check("choosing «Все» clears the type from the address", "type=" not in pg.url, pg.url.replace(BASE, ""))

            # The export button names itself instead of leaving an icon to be guessed at:
            # a word anyone can see, not only one a screen reader gets from aria-label.
            export_label = await pg.evaluate(
                "() => { const b = [...document.querySelectorAll('button')]"
                ".find(x => x.innerText.includes('Экспорт') || /Экспорт/.test(x.getAttribute('aria-label') || ''));"
                " return b ? b.innerText.trim() : ''; }"
            )
            check("the export button says what it is, in words", export_label == "Экспорт", repr(export_label))

            # The swipe hint belongs to both lists and is said once: the key is the app's own.
            await pg.evaluate("localStorage.removeItem('petzy:swipeHintSeen')")
            await pg.goto(BASE + "/history")
            await pg.wait_for_timeout(2200)
            check(
                "the swipe hint is on the History screen too",
                "Смахните запись" in (await pg.inner_text("body")),
            )
            await pg.get_by_role("button", name="Понятно").click()
            await pg.wait_for_timeout(600)
            await pg.goto(BASE + "/")
            await pg.wait_for_timeout(2500)
            check(
                "and said once: the feed does not repeat it",
                "Смахните запись" not in (await pg.inner_text("body")),
            )

            # The form says whose record this is, and who wrote it, whichever line it is.
            await pg.goto(BASE + "/history?type=weight")
            await pg.wait_for_timeout(2200)
            await pg.locator("[aria-label$=', открыть']").first.click()
            await pg.wait_for_timeout(2200)
            head = await pg.inner_text("body")
            check("the form opens the record for editing", "/form/weight/" in pg.url, pg.url.replace(BASE, ""))
            check("the address carries no unused parameter", "tab=" not in pg.url, pg.url.replace(BASE, ""))
            check(f"the form names the pet ({PET})", f"Питомец: {PET}" in head, head[:200].replace(chr(10), " | "))

            # The name the saved one is empty (a cleared storage, a fresh install): the line still stands.
            await pg.evaluate("localStorage.setItem('selectedPetName', 'null')")
            await pg.reload()
            await pg.wait_for_timeout(2500)
            head = await pg.inner_text("body")
            check(
                "the pet's name comes from the pet, not only from the saved one",
                f"Питомец: {PET}" in head,
                head[:200].replace(chr(10), " | "),
            )
            check(
                "and who wrote the record is said on its own line",
                "Записал(а):" in head,
                head[:200].replace(chr(10), " | "),
            )
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("history screen")


asyncio.run(main())
