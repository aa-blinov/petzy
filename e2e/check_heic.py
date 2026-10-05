"""A phone's HEIC photo is drawn in Chrome too: the thumbnail of a picked file in the record form and the crop window of a pet's photo.

Needs the local stack and the demo data. Makes a HEIC file of its own in /tmp."""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary

HEIC = "/tmp/check_heic.heic"


def make_heic() -> None:
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    Image.new("RGB", (800, 600), (196, 106, 63)).save(HEIC, format="HEIF")


async def main():
    make_heic()
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        await pg.goto(BASE + f"/pets/{rex}/medical-records/new?kind=visit")
        await pg.wait_for_timeout(1800)
        await pg.locator("input[capture]").set_input_files(HEIC)
        await pg.wait_for_timeout(1500)
        widths = await pg.evaluate("[...document.querySelectorAll('.medrec__file-thumb')].map(i => i.naturalWidth)")
        check("the thumbnail of a picked HEIC is a picture", widths == [800], str(widths))
        await pg.goto(BASE + "/pets/new")
        await pg.wait_for_timeout(1800)
        await pg.locator("#pet-photo-input").set_input_files(HEIC)
        await pg.wait_for_timeout(2500)
        crop = await pg.evaluate("[...document.querySelectorAll('img.reactEasyCrop_Image')].map(i => i.naturalWidth)")
        check("the crop window of a pet's photo shows a picked HEIC", crop == [800], str(crop))
        await b.close()
    summary("HEIC in Chrome")


asyncio.run(main())
