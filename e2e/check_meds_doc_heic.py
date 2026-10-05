"""The document form shows a picked phone photo instead of only its name: a HEIC is what a phone's camera
gives, and Chrome draws nothing of it, so the row now asks the server for a WebP to look at (nothing is stored).

Needs the local stack and the demo data. Makes a HEIC file of its own in /tmp and throws it away."""

import asyncio
import os

from common import BASE, async_playwright, check, login, new_page, summary

HEIC = "/tmp/check_meds_doc_heic.heic"


def make_heic() -> None:
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    Image.new("RGB", (800, 600), (94, 122, 168)).save(HEIC, format="HEIF")


async def main():
    make_heic()
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        try:
            await pg.goto(BASE + "/documents/new")
            await pg.wait_for_timeout(2000)
            await pg.locator("#document-file-input").set_input_files(HEIC)
            await pg.wait_for_timeout(3500)
            row = pg.locator("#document-file-input").locator("xpath=..")
            shown = await row.evaluate(
                """e => { const img = e.querySelector('img'); return img ? [img.naturalWidth, img.naturalHeight] : null; }"""
            )
            check("the chosen phone photo is shown, not only named", shown == [800, 600], str(shown))
            check(
                "the file's name is still there",
                "check_meds_doc_heic" in await row.inner_text(),
                (await row.inner_text()).replace("\n", " | ")[:120],
            )
            check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        finally:
            if os.path.exists(HEIC):
                os.remove(HEIC)
        await b.close()
    summary("a phone photo in the document form")


asyncio.run(main())
