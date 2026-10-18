"""Документы: архив, выбранный в общем выборе файла, сам попадает в «Снимки».

The sheet has no tile of its own for scans: an archive is one of the files. Picking one opens the form with it, and the
category «Снимки» is already set. Nothing is saved: the check leaves the form without submitting.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, settle, summary

# A zip header and some bytes: the form looks at the name and the size, not at the content.
ARCHIVE = b"PK\x03\x04" + b"0" * 64


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        await pg.goto(BASE + "/documents")
        await settle(pg, 150)
        await pg.locator(".app-fab").click()
        await settle(pg, 150)
        check(
            "the sheet has the camera and one files tile, with no tile of its own for scans",
            await pg.locator(".recsheet__label").all_inner_texts()
            == ["Сфотографировать", "Фото, PDF или архив из файлов"],
        )
        await pg.locator('input[aria-label="Выбрать файл"]').set_input_files(
            {"name": "снимки-мрт.zip", "mimeType": "application/zip", "buffer": ARCHIVE}
        )
        await pg.wait_for_url(lambda url: "/documents/new" in url, timeout=15000)
        await settle(pg, 150)
        check("the archive opens the form with its name", await pg.get_by_text("снимки-мрт.zip").count() > 0)
        check("and the category is «Снимки» already", await pg.get_by_text("Снимки", exact=True).count() > 0)
        await b.close()
    summary("the archive from the files tile")


asyncio.run(main())
