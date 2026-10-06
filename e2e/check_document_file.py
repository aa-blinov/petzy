"""Документы: «Добавлен» по зоне документа и замена файла при правке.

The browser stands in a zone of its own (New York), the document is added
with another one (Almaty): the time under its title has to be the document's,
not the phone's. Then the file is replaced from the form, which used to say
that a file could only be changed by deleting the document.
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from common import BASE, api, async_playwright, check, login, summary

PDF_OLD = b"%PDF-1.4 old"
PDF_NEW = b"%PDF-1.4 new"


async def new_page(b):
    """A phone-sized page in a zone that is not the document's."""
    ctx = await b.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        is_mobile=True,
        locale="ru-RU",
        color_scheme="light",
        service_workers="block",
        timezone_id="America/New_York",
    )
    return ctx, await ctx.new_page()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b)
        await login(pg, "demo", "Рекс")
        await pg.goto(BASE + "/pets/new")
        await pg.wait_for_timeout(1200)
        await pg.get_by_role("button", name="Собака").click()
        await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
        await pg.get_by_role("button", name="Добавить", exact=True).click()
        await pg.wait_for_timeout(2200)
        await pg.get_by_role("button", name="Готово").click()
        await pg.wait_for_timeout(800)
        pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
        try:
            # A document added in Almaty's zone, whatever clock the phone has.
            await pg.evaluate(
                """async ([pid, tz]) => {
                    const fd = new FormData();
                    fd.append('pet_id', pid);
                    fd.append('category', 'other');
                    fd.append('title', 'Смена файла');
                    fd.append('tz', tz);
                    fd.append('file', new File([new Uint8Array([37, 80, 68, 70, 45, 49, 46, 52, 32, 111, 108, 100])], 'старое.pdf', {type: 'application/pdf'}));
                    await fetch('/api/documents', {method: 'POST', body: fd, credentials: 'include'});
                }""",
                [pid, "Asia/Almaty"],
            )
            docs = (await api(pg, "GET", f"/documents?pet_id={pid}"))["json"]["documents"]
            doc = docs[0]
            doc_id = doc["_id"]

            await pg.goto(BASE + "/documents")
            await pg.wait_for_timeout(1800)
            row = pg.get_by_text("Смена файла").first
            card = row.locator("xpath=ancestor::*[contains(@class,'adm-card')][1]")
            line = await card.inner_text()
            # created_at в ответе это метка UTC: время документа считается из неё по его собственной зоне.
            added = (
                datetime.strptime(doc["created_at"], "%Y-%m-%d %H:%M")
                .replace(tzinfo=ZoneInfo("UTC"))
                .astimezone(ZoneInfo("Asia/Almaty"))
            )
            check(
                "«Добавлен» is the document's own time, not the phone's",
                f"Добавлен сегодня в {added:%H:%M}" in line,
                line.replace(chr(10), " | "),
            )

            # Правка: the file can be replaced from the form.
            await pg.goto(BASE + f"/documents/{doc_id}/edit")
            await pg.wait_for_timeout(1800)
            form_text = await pg.inner_text("body")
            check(
                "the form no longer tells the file has to be deleted",
                "Чтобы заменить файл" not in form_text and "старое.pdf" in form_text,
                form_text[:200].replace(chr(10), " | "),
            )
            await pg.get_by_text("Заменить файл", exact=True).click()
            await pg.wait_for_timeout(400)
            await pg.locator("#document-file-input").set_input_files(
                files=[{"name": "новое.pdf", "mimeType": "application/pdf", "buffer": PDF_NEW}]
            )
            await pg.wait_for_timeout(900)
            check(
                "the chosen file is offered for the swap, with a way back",
                await pg.get_by_text("Новый файл заменит прежний").count() == 1
                and await pg.get_by_text("Оставить прежний файл").count() == 1,
            )
            await pg.get_by_role("button", name="Сохранить").click()
            await pg.wait_for_timeout(2500)
            after = (await api(pg, "GET", f"/documents/{doc_id}"))["json"]["document"]
            check(
                "the document keeps its id and gets the new file",
                after["original_filename"] == "новое.pdf"
                and after["file_size"] == len(PDF_NEW)
                and after["title"] == "Смена файла",
                json_str(after),
            )
            await pg.goto(BASE + "/documents")
            await pg.wait_for_timeout(1800)
            body = await pg.inner_text("body")
            check(
                # Список показывает название, категорию, тип, дату и размер, а не имя файла; что файл новый,
                # уже сказано ответом сервера строкой выше. Здесь проверяем, что документ на месте и старая
                # подсказка про удаление исчезла вместе с возможностью заменить файл.
                "the list still shows the document and the old note is gone",
                "Смена файла" in body and "Чтобы заменить файл" not in body,
                body[:200].replace(chr(10), " | "),
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await ctx.close()
        await b.close()
    summary("document zone and file replacement")


def json_str(value):
    import json

    return json.dumps(value, ensure_ascii=False)[:160]


asyncio.run(main())
