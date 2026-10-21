"""The top bar stays on the screen while a field is typed in and iOS pans the viewport to show it.

A pan that outlives the keyboard is a leftover and the bars come home from it: a form closed by a
navigation takes its field away without a focusout, and following the pan it left dragged the tab
bar off the bottom edge and the header under the notch.

With the keyboard up, iOS pans the visual viewport so that the field shows above the keys. A top bar fixed in place floats
out of the screen by that pan, so utils/keyboard.ts moves it by `--vv-shift` the same as without a keyboard. The tab bar
and the add button are hidden while the keyboard is up. While the keyboard is still coming up, the tab bar follows the pan
too, and once the keyboard is gone it sits on the bottom edge again.

Headless Chromium never pans and shows no keyboard, so this makes both: the viewport getters are replaced, as in
check_bar_stays, and the page's own field takes the focus that opens the keyboard in the app.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

PAN = 120
KEYBOARD = 300

# The visual viewport is panned down by `offset` and loses the keyboard's rows from its bottom, as on an iPhone.
VIEWPORT = """([offset, keyboard]) => {
  if (window.__realVvHeight === undefined) window.__realVvHeight = window.visualViewport.height;
  const realHeight = window.__realVvHeight;
  Object.defineProperty(VisualViewport.prototype, 'offsetTop', { get: () => offset, configurable: true });
  Object.defineProperty(VisualViewport.prototype, 'height', { get: () => realHeight - keyboard, configurable: true });
  window.visualViewport.dispatchEvent(new Event('resize'));
}
"""

READ = """
() => {
  const vv = window.visualViewport;
  const root = document.documentElement;
  const header = document.querySelector('header').getBoundingClientRect();
  const bar = document.querySelector('.bottom-tab-bar-container');
  const shown = getComputedStyle(bar).display !== 'none';
  return {
    open: root.classList.contains('keyboard-open'),
    shift: getComputedStyle(root).getPropertyValue('--vv-shift').trim(),
    headerTop: Math.round(header.top - vv.offsetTop),
    barBottom: shown ? Math.round(bar.getBoundingClientRect().bottom - vv.offsetTop) : null,
    visibleBottom: Math.round(vv.height),
  };
}
"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx, pg = await new_page(browser, width=393, height=659)
        await login(pg, "demo", "Рекс")
        await pg.goto(BASE + "/pets/new")
        await pg.wait_for_timeout(800)
        field = pg.locator("input:not([readonly]):not([type=checkbox]):not([type=radio])").first

        await field.click()
        await pg.evaluate(VIEWPORT, [PAN, 0])
        await pg.wait_for_timeout(200)
        read = await pg.evaluate(READ)
        check(
            "the keyboard is still coming up, and the tab bar follows the pan",
            read["barBottom"] == read["visibleBottom"],
            str(read),
        )

        await pg.evaluate(VIEWPORT, [PAN, KEYBOARD])
        await pg.wait_for_timeout(200)
        read = await pg.evaluate(READ)
        check("with the keyboard up, the page knows it", read["open"], str(read))
        check("and the top bar stays at the top of the visible screen", abs(read["headerTop"]) <= 1, str(read))
        check("it moves by the pan", read["shift"] == f"{PAN}px", str(read))

        await pg.evaluate("() => document.activeElement && document.activeElement.blur()")
        await pg.evaluate(VIEWPORT, [PAN, 0])
        await pg.wait_for_timeout(400)
        read = await pg.evaluate(READ)
        check(
            "with the keyboard gone and the pan left, the tab bar sits on the bottom edge",
            read["barBottom"] == read["visibleBottom"],
            str(read),
        )
        check("and the top bar is still on the top", abs(read["headerTop"]) <= 1, str(read))

        # The page that had the field is left by navigating away: the field disappears with it, no
        # focusout ever comes, and the pan the keyboard left stays. The bars must not follow it.
        await pg.goto(BASE + "/pets/new")
        await pg.wait_for_timeout(700)
        field = pg.locator("input:not([readonly]):not([type=checkbox]):not([type=radio])").first
        await field.click()
        await pg.evaluate(VIEWPORT, [PAN, KEYBOARD])
        await pg.wait_for_timeout(250)
        await pg.evaluate(VIEWPORT, [PAN, 0])
        await pg.go_back()
        await pg.wait_for_timeout(900)
        read = await pg.evaluate(READ)
        check(
            "a form left by going back takes its pan with it: no shift is left behind",
            read["shift"] == "0px" and not read["open"],
            str(read),
        )
        check(
            "and the bars are home again, not dragged down by the leftover pan",
            abs(read["headerTop"]) <= 1 and read["barBottom"] == read["visibleBottom"],
            str(read),
        )
        # The pan is still reported after the page that had the field is gone (iOS keeps it), so a
        # scroll of the feed must not pick it up again: the leftover holds until the viewport comes
        # home by itself.
        await pg.evaluate("() => window.scrollBy(0, 240)")
        await pg.wait_for_timeout(400)
        read = await pg.evaluate(READ)
        check(
            "и прокрутка ленты не подхватывает оставшуюся панораму снова",
            read["shift"] == "0px" and abs(read["headerTop"]) <= 1 and read["barBottom"] == read["visibleBottom"],
            str(read),
        )

        await browser.close()
    summary("the top bar with the keyboard up")


asyncio.run(main())
