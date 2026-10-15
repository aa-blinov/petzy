"""Scrolling never moves the bars; a viewport left panned moves both of them.

On iPhone the end of a page springs back, and while it does the visual viewport reports an offset for a moment.
utils/keyboard.ts used to move the tab bar by it on every scroll of the visual viewport, and nudge the page: the bar
jumped at the bottom of every page and the momentum broke. Now a scroll may only take a shift away. A viewport really
left panned (after the keyboard, or back from another app) is found on a resize, and then the top bar follows the
shift too: it used to stay where it was and go up under the Dynamic Island.

Headless Chromium never pans, so the offset is faked and the events the app listens for are fired by hand.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

FAKE = """([offset, event]) => {
  if (!window.__vvOriginal) {
    window.__vvOriginal = {
      offsetTop: Object.getOwnPropertyDescriptor(VisualViewport.prototype, 'offsetTop'),
      height: Object.getOwnPropertyDescriptor(VisualViewport.prototype, 'height'),
    };
    window.__vvHeight = window.visualViewport.height;
  }
  Object.defineProperty(VisualViewport.prototype, 'offsetTop', { get: () => offset, configurable: true });
  Object.defineProperty(VisualViewport.prototype, 'height', { get: () => window.__vvHeight, configurable: true });
  window.visualViewport.dispatchEvent(new Event(event));
}"""

RESTORE = """() => {
  const o = window.__vvOriginal;
  if (!o) return;
  Object.defineProperty(VisualViewport.prototype, 'offsetTop', o.offsetTop);
  Object.defineProperty(VisualViewport.prototype, 'height', o.height);
  delete window.__vvOriginal;
  window.visualViewport.dispatchEvent(new Event('resize'));
}"""

READ = """() => ({
  shift: getComputedStyle(document.documentElement).getPropertyValue('--vv-shift').trim(),
  header: getComputedStyle(document.querySelector('header')).translate,
})"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx, pg = await new_page(browser, width=393, height=659)
        await login(pg)
        await pg.goto(BASE + "/")
        await pg.wait_for_selector(".bottom-tab-bar-container", timeout=20000)
        await pg.wait_for_timeout(700)

        await pg.evaluate(FAKE, [40, "scroll"])
        await pg.wait_for_timeout(300)
        got = await pg.evaluate(READ)
        check("a scroll with a springing offset does not move the bars", got["shift"] in ("0px", ""), str(got))

        await pg.evaluate(FAKE, [40, "resize"])
        await pg.wait_for_timeout(300)
        got = await pg.evaluate(READ)
        check(
            "a viewport left panned (found on a resize) moves the tab bar back to the edge",
            got["shift"] == "40px",
            str(got),
        )
        check(
            "and the top bar follows it, instead of going up under the island", "40px" in str(got["header"]), str(got)
        )

        await pg.evaluate(FAKE, [0, "scroll"])
        await pg.wait_for_timeout(300)
        got = await pg.evaluate(READ)
        check("a scroll that brings the viewport back takes the shift away", got["shift"] == "0px", str(got))

        await pg.evaluate(RESTORE)
        await ctx.close()
        await browser.close()
    summary("bars and the springing end of a page")


asyncio.run(main())
