"""Nothing of the bottom bar paints over the page above it.

The active icon grows to 1.12 and its Material 3 indicator is drawn 4px above
the icon, which put the indicator's top edge above the top of the bar and a row
of its colour showed on the page. Half a pixel of layout is nothing and a
visible hairline on a phone, which is what the person saw.

Geometry cannot catch this: clipping the bar leaves the box exactly where it
was, it just stops the painting. So this looks at pixels. The strip of rows
just above the bar is read from a screenshot, and nothing in it may be the
indicator's colour, which the stylesheet hands over as a token.
"""

import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary  # noqa: E402
from PIL import Image  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

ROWS_ABOVE = 4  # the bar was over by under two pixels
TOLERANCE = 8  # the pill is solid; only its anti-aliased edge is a shade off, the page behind is further


def _dominant(image, box=None):
    """The most common colour in an image, which is the bar's or the indicator's own paint."""
    cropped = image if box is None else image.crop(box)
    counts = {}
    for y in range(cropped.height):
        for x in range(cropped.width):
            colour = cropped.getpixel((x, y))
            counts[colour] = counts.get(colour, 0) + 1
    return max(counts, key=counts.get)


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for width in (390, 360, 320):
            ctx, pg = await new_page(browser, width=width, height=844)
            await login(pg, "demo", "Рекс")
            await pg.goto(BASE + "/")
            await pg.wait_for_selector(".bottom-tab-bar-container", timeout=20000)
            await pg.wait_for_selector(".app-tab-bar__item--active", timeout=20000)
            await pg.wait_for_timeout(800)
            # The swipe hint is a banner of the same apricot as the indicator and may stand right above the bar on a short feed:
            # it is content, not paint that spilled over, so it is dismissed before the strip above the bar is read.
            if await pg.get_by_role("button", name="Понятно").count():
                await pg.get_by_role("button", name="Понятно").click()
                await pg.wait_for_timeout(500)

            bar_top, centre = await pg.evaluate("""() => {
              const bar = document.querySelector('.bottom-tab-bar-container').getBoundingClientRect();
              const active = document.querySelector('.app-tab-bar__item--active').getBoundingClientRect();
              return [Math.round(bar.top), Math.round(active.left + active.width / 2)];
            }""")

            # The indicator's own paint, read from inside the bar where it is solid.
            inside = Image.open(
                io.BytesIO(await pg.screenshot(clip={"x": centre - 12, "y": bar_top + 10, "width": 24, "height": 3}))
            ).convert("RGB")
            reference = _dominant(inside)

            # And the page just above the bar.
            above = Image.open(
                io.BytesIO(
                    await pg.screenshot(clip={"x": 0, "y": bar_top - ROWS_ABOVE, "width": width, "height": ROWS_ABOVE})
                )
            ).convert("RGB")
            found = [
                (x, bar_top - ROWS_ABOVE + y, above.getpixel((x, y)))
                for y in range(above.height)
                for x in range(above.width)
                if all(abs(c - r) <= TOLERANCE for c, r in zip(above.getpixel((x, y)), reference))
            ]
            check(
                f"{width}px: над навбаром нет цвета подсветки",
                not found,
                f"подсветка внутри {reference}, и та же краска в {len(found)} пикселях над строкой {bar_top},"
                f" первый в {found[0] if found else None}",
            )
            await ctx.close()
        await browser.close()
    summary("the bottom bar paints nothing over the page")


asyncio.run(main())
