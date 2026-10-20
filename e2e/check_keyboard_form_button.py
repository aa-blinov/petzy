"""The button that closes a long form stays above the keys.

A phone's keyboard covers the bottom of the page and only the visual viewport shrinks: the layout
viewport stays as tall as the screen, and a button held to the bottom of it (position: sticky)
ends up behind the keys, where it cannot be pressed. utils/keyboard.ts writes how much the keys
cover into `--keyboard-fixed-offset`, and the button rides on the top edge of the keys.

Headless Chromium shows no keyboard, so the visual viewport is faked, as in check_bar_keyboard_pan:
its height loses the rows of the keys, and the page's own field takes the focus that opens them.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

KEYBOARD = 300

# The visual viewport loses the rows of the keys, as on a phone whose layout viewport keeps its size.
VIEWPORT = """([keyboard]) => {
  if (window.__realVvHeight === undefined) window.__realVvHeight = window.visualViewport.height;
  const realHeight = window.__realVvHeight;
  Object.defineProperty(VisualViewport.prototype, 'height', { get: () => realHeight - keyboard, configurable: true });
  window.visualViewport.dispatchEvent(new Event('resize'));
}
"""

READ = """
() => {
  const vv = window.visualViewport;
  const root = document.documentElement;
  const button = document.querySelector('.form-sticky-action');
  const field = document.activeElement;
  const box = (el) => (el ? el.getBoundingClientRect() : null);
  const bar = document.querySelector('.bottom-tab-bar-container');
  return {
    open: root.classList.contains('keyboard-open'),
    offset: getComputedStyle(root).getPropertyValue('--keyboard-fixed-offset').trim(),
    visibleBottom: Math.round(vv.height),
    buttonBottom: button ? Math.round(box(button).bottom) : null,
    fieldBottom: field ? Math.round(box(field).bottom) : null,
    tabBarShown: bar ? getComputedStyle(bar).display !== 'none' : null,
    tabBarTop: bar ? Math.round(box(bar).top) : null,
  };
}
"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx, pg = await new_page(browser, width=393, height=659)
        rex = await login(pg, "demo", "Рекс")
        await pg.goto(BASE + f"/pets/{rex}/visit-prep")
        await pg.wait_for_timeout(900)
        field = pg.locator("textarea:not([readonly])").first
        check(
            "the form has a field to type in and a button to close it",
            await field.count() == 1,
            str(await field.count()),
        )

        await field.click()
        await pg.wait_for_timeout(200)
        read = await pg.evaluate(READ)
        check(
            "without the keyboard the button sits on the tab bar, the bottom of the screen",
            read["buttonBottom"] <= read["tabBarTop"],
            str(read),
        )

        await pg.evaluate(VIEWPORT, [KEYBOARD])
        await pg.wait_for_timeout(300)
        read = await pg.evaluate(READ)
        check("with the keyboard up, the page knows it", read["open"], str(read))
        check(
            "and the button is above the keys, not behind them",
            read["buttonBottom"] <= read["visibleBottom"],
            str(read),
        )
        check(
            "and the field being typed in is above the keys too",
            read["fieldBottom"] <= read["visibleBottom"],
            str(read),
        )
        check("the tab bar steps aside while the keys are up", read["tabBarShown"] is False, str(read))

        await pg.evaluate("() => document.activeElement && document.activeElement.blur()")
        await pg.evaluate(VIEWPORT, [0])
        await pg.wait_for_timeout(300)
        read = await pg.evaluate(READ)
        check(
            "and with the keys gone the button sits on the tab bar again",
            read["buttonBottom"] <= read["tabBarTop"] and read["tabBarShown"] is True,
            str(read),
        )

        await browser.close()
    summary("the button of a form and the keyboard")


asyncio.run(main())
