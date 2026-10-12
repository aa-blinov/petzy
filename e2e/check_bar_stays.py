"""The bottom bar cannot leave the screen, whatever the visual viewport says.

A bottom-fixed bar is moved down by `--vv-shift`, which utils/keyboard.ts takes
from `visualViewport.offsetTop`. That offset is non-zero on iOS when the
viewport is left panned inside the page: after a keyboard is closed, after the
app is left and returned to, and after a slight pinch-zoom. The code nudges the
page to bring the viewport back, but at the end of a page there is nowhere to
nudge to, and then the offset stays: a stale number that moves the bar straight
down and off the bottom edge. That is the bar «улетающий» вниз on iPhone Chrome.

Headless Chromium never pans, so this makes it: the getter is replaced and the
resize event the app listens for is fired, with the viewport offset by more than
the bar's height, which is the worst a stale offset can be.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

# A stale pan: the viewport sits `offset` rows lower and is that much shorter,
# so the edge of the visible area lands exactly where the bar already is. The
# offset number is real and non-zero, which is exactly the trap: trusting it
# moves the bar past the edge for nothing. Faking only offsetTop would leave
# the edge below the bar and make the shift genuinely necessary, which would
# make this check pass either way and prove nothing.
PANNED = """(offset) => {
  if (window.__realVvHeight === undefined) window.__realVvHeight = window.visualViewport.height;
  const realHeight = window.__realVvHeight;
  Object.defineProperty(VisualViewport.prototype, 'offsetTop', { get: () => offset, configurable: true });
  Object.defineProperty(VisualViewport.prototype, 'height', { get: () => realHeight - offset, configurable: true });
  window.visualViewport.dispatchEvent(new Event('resize'));
}
"""

READ = """
() => {
  const bar = document.querySelector('.bottom-tab-bar-container').getBoundingClientRect();
  const vv = window.visualViewport;
  return {
    shift: getComputedStyle(document.documentElement).getPropertyValue('--vv-shift').trim(),
    below: Math.round(bar.bottom - (vv.offsetTop + vv.height)),
    onScreen: Math.round(bar.bottom - vv.offsetTop),
  };
}
"""


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # iPhone in Chrome: no Safe Area inset, the browser's own bar sits below.
        ctx, pg = await new_page(browser, width=393, height=659)
        await login(pg, "demo", "Рекс")

        for path in ("/", "/medications", "/documents", "/settings"):
            await pg.goto(BASE + path)
            await pg.wait_for_selector(".bottom-tab-bar-container", timeout=20000)
            await pg.wait_for_timeout(700)

            for offset in (24, 80):
                await pg.evaluate(PANNED, offset)
                await pg.wait_for_timeout(500)
                got = await pg.evaluate(READ)
                check(
                    f"{path}: при сдвиге окна на {offset} px нижняя полоса остаётся на экране",
                    got["below"] <= 0,
                    f"сдвиг {got['shift']}, полоса уходит за видимую область на {got['below']} px",
                )
            # Put the getter back so the next screen starts honest.
            await pg.evaluate(
                "() => { delete VisualViewport.prototype.offsetTop; delete VisualViewport.prototype.height;"
                " delete window.__realVvHeight; window.visualViewport.dispatchEvent(new Event('resize')); }"
            )
            await pg.wait_for_timeout(400)

        await ctx.close()
        await browser.close()
    summary("the bottom bar never leaves the screen")


asyncio.run(main())
