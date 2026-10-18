"""Documents as an archive: a file says which record holds it, opens that record, and is found by what the record says.

Needs the local stack and the demo data (docker compose -p petzy-local ... up, scripts/seed_demo.py)."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, settle


async def titles(pg):
    return [t.strip() for t in await pg.locator("h3").all_inner_texts()]


def ddmmyyyy(iso):
    year, month, day = iso.split("-")
    return f"{day}.{month}.{year}"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        pid = await login(pg, "demo", "Рекс")
        # The visit's day is read off the server: the seed sets it relative to the day it ran, so it is not written here.
        records = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
        visit_days = [ddmmyyyy(r["date"]) for r in records if r.get("title") == "Плановый осмотр"]
        await pg.goto(BASE + "/documents")
        await settle(pg)
        sources = await pg.locator(".docs__source").all_inner_texts()
        check(
            "a document held by a record says «Из записи» with its title and day",
            any(f"Плановый осмотр, {day}" in s for day in visit_days for s in sources),
            str(sources),
        )
        check(
            "a document held by no record says nothing of the kind",
            "Страховка на год" in await titles(pg) and len(sources) < len(await titles(pg)),
        )
        check(
            "the add button is the round plus at the bottom, not a link at the top",
            await pg.locator(".app-fab").count() == 1
            and await pg.get_by_role("button", name="Добавить", exact=True).count() == 0,
        )
        check("a row does not repeat the file's name under its title", await pg.get_by_text(".pdf").count() == 0)
        await pg.locator(".app-fab").click()
        await settle(pg, 150)
        check(
            "it opens a sheet with the camera and the files, archives among them",
            await pg.locator(".recsheet__label").all_inner_texts()
            == ["Сфотографировать", "Фото, PDF или архив из файлов"],
        )
        await pg.keyboard.press("Escape")
        await pg.mouse.click(195, 60)
        await settle(pg, 150)
        search = pg.locator(".adm-search-bar input")
        await search.fill("плановый осмотр")
        await pg.wait_for_timeout(400)
        check(
            "it is found by the reason of the visit that holds it",
            await titles(pg) == ["Анализ крови"],
            str(await titles(pg)),
        )
        await search.fill("ортовет")
        await pg.wait_for_timeout(400)
        check(
            "it is found by the clinic of the record",
            "Анализ крови" in await titles(pg) and "Страховка на год" not in await titles(pg),
            str(await titles(pg)),
        )
        await search.fill("анализ ортовет")
        await pg.wait_for_timeout(400)
        check("several words must all be there", await titles(pg) == ["Анализ крови"], str(await titles(pg)))
        shown_day = next((day for day in visit_days if any(f"Плановый осмотр, {day}" in s for s in sources)), "")
        await search.fill(shown_day)
        await pg.wait_for_timeout(400)
        check("it is found by the day of the record", await titles(pg) == ["Анализ крови"], str(await titles(pg)))
        await search.fill("")
        await pg.wait_for_timeout(300)
        await pg.locator(".docs__source", has_text="Плановый осмотр").click()
        await settle(pg, 150)
        check("the line opens the record", "/medical-records/" in pg.url, pg.url.replace(BASE, ""))
        # the form says at once what is not a photo or a PDF, and does not take it
        note = "/private/tmp/check_documents_note.txt"
        with open(note, "w", encoding="utf-8") as f:
            f.write("not a photo")
        await pg.goto(BASE + "/documents/new")
        await settle(pg)
        await pg.locator("#document-file-input").set_input_files(note)
        await pg.wait_for_timeout(500)
        errors = [t.strip() for t in await pg.locator(".field-error").all_inner_texts()]
        check(
            "a text file is refused by the form with the reason",
            any("подходят фото и PDF" in e for e in errors),
            str(errors),
        )
        check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        await b.close()
    summary("documents as an archive")


asyncio.run(main())
