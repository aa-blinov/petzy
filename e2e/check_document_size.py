"""Документы: файл больше 10 МБ отклоняется при выборе, и причина не пропадает.

A file over the limit is refused the moment it is picked, with the reason. Sending the form
without a new file used to replace that reason with «Выберите фото или PDF», so the person
was not told why nothing was added. No document is made from the refused file.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

SCRATCH_PET = "Тест-М-2"
BIG_PDF = b"%PDF-1.4\n" + b"0" * (11 * 1024 * 1024)


async def make_pet(pg):
    await pg.goto(BASE + "/pets/new")
    await pg.wait_for_timeout(800)
    await pg.get_by_role("button", name="Собака").click()
    await pg.get_by_placeholder("Имя питомца").fill(SCRATCH_PET)
    await pg.get_by_role("button", name="Добавить", exact=True).click()
    await pg.wait_for_timeout(2200)
    if await pg.get_by_role("button", name="Готово").count():
        await pg.get_by_role("button", name="Готово").click()
    await pg.wait_for_timeout(800)
    pets = (await api(pg, "GET", "/pets"))["json"]["pets"]
    return next(q["_id"] for q in pets if q["name"] == SCRATCH_PET)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx, pg = await new_page(browser, width=390, height=844)
        await login(pg, "demo", "Рекс")
        pid = None
        try:
            pid = await make_pet(pg)
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, SCRATCH_PET],
            )
            await pg.goto(BASE + "/documents/new")
            await pg.wait_for_timeout(1000)
            await pg.get_by_text("Выберите категорию").first.click()
            await pg.wait_for_timeout(600)
            await pg.get_by_role("button", name="Готово").last.click()
            await pg.wait_for_timeout(500)
            await pg.get_by_placeholder("Например, Прививка от бешенства").fill("Большой файл")
            await pg.locator("#document-file-input").set_input_files(
                files=[{"name": "большой.pdf", "mimeType": "application/pdf", "buffer": BIG_PDF}]
            )
            await pg.wait_for_timeout(900)
            picked = await pg.inner_text("body")
            check(
                "a file over 10 MB is refused the moment it is picked, with the reason",
                "Файл больше 10 МБ" in picked,
                picked[picked.find("Файл больше") - 20 : picked.find("Файл больше") + 90].replace(chr(10), " | ")
                if "Файл больше" in picked
                else "no reason on the form",
            )
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.wait_for_timeout(2000)
            sent = await pg.inner_text("body")
            check(
                "sending without a file keeps the reason instead of «Выберите фото или PDF»",
                "Файл больше 10 МБ" in sent and "Выберите фото или PDF" not in sent,
                sent[sent.find("Файл") : sent.find("Файл") + 110].replace(chr(10), " | "),
            )
            docs = (await api(pg, "GET", f"/documents?pet_id={pid}"))["json"]["documents"]
            check("no document is made from the refused file", all(d.get("title") != "Большой файл" for d in docs))
        finally:
            if pid:
                await api(pg, "DELETE", f"/pets/{pid}")
        await ctx.close()
        await browser.close()
    summary("a file over the limit keeps its reason")


asyncio.run(main())
