"""The bottom bar stays where it is while Chrome moves the ground under it.

Chrome on iPhone does not keep the page the same size while you read it. The
address bar at the bottom shrinks as you scroll down and is gone once you are
far enough, and the web viewport grows by the same amount. That is a real
device behaviour, so this drives it: a genuine iPhone profile, a viewport that
starts at what is left under the expanded bar and grows as the bar hides, and
the bar measured at each step.

The bar is fixed to the bottom and the page's own height is in `100dvh`, so
every step changes both. What must hold at every step is that the bar is still
whole on the screen. Whether it paints anything above its own edge is a
separate question, asked of the pixels by e2e/check_tab_bar.py.

The pan case from the keyboard is a separate check (e2e/check_bar_stays.py):
headless Chromium never pans the visual viewport, so it can only be faked.

Chrome's toolbar does not only change the height: when it collapses, the visual viewport is panned
too, and the page hears a scroll rather than a resize (Chromium issues 504094431 and 417426570). A
fixed header left in place then sits above the visible area, under the clock. That pan is one jump
and then it stays, which is what tells it apart from the spring-back at the end of a page: the
header follows it once it has settled.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

# Chrome's own bottom bar: roughly a thumb's height when it is there, gone when
# it is not. The web viewport is what the page gets to work with.
CHROME_BAR = {"expanded": 148, "hidden": 50}

READ = """
() => {
  const bar = document.querySelector('.bottom-tab-bar-container').getBoundingClientRect();
  const strip = document.querySelector('.app-tab-bar').getBoundingClientRect();
  const vv = window.visualViewport;
  const root = getComputedStyle(document.documentElement);
  return {
    barTop: Math.round(bar.top), barBottom: Math.round(bar.bottom),
    stripTop: Math.round(strip.top),
    below: Math.round(bar.bottom - (vv.offsetTop + vv.height)),
    above: Math.round(vv.offsetTop + vv.height - strip.top),
    shift: root.getPropertyValue('--vv-shift').trim(),
    dvh: root.getPropertyValue('--app-vh').trim(),
    atEnd: Math.round(window.scrollY + window.innerHeight) >= Math.round(document.documentElement.scrollHeight) - 2,
  };
}
"""


async def resize(cdp, width, height):
    """What the browser does to the page when it takes its own bar away."""
    await cdp.send(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": height, "deviceScaleFactor": 3, "mobile": True},
    )


PANNED = 60

PAN = """(offset) => {
  if (window.__realVvHeight === undefined) window.__realVvHeight = window.visualViewport.height;
  const real = window.__realVvHeight;
  Object.defineProperty(VisualViewport.prototype, 'offsetTop', { get: () => offset, configurable: true });
  Object.defineProperty(VisualViewport.prototype, 'height', { get: () => real - offset, configurable: true });
  window.visualViewport.dispatchEvent(new Event('scroll'));
}
"""

HEADER_TOP = """() => {
  const vv = window.visualViewport;
  return Math.round(document.querySelector('header').getBoundingClientRect().top - vv.offsetTop);
}
"""


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        device = p.devices["iPhone 14 Pro"]
        width, full = device["viewport"]["width"], device["viewport"]["height"]

        ctx, pg = await new_page(browser, width=width, height=full - CHROME_BAR["expanded"], sw=True)
        await login(pg, "demo", "Рекс")
        cdp = await ctx.new_cdp_session(pg)

        for path in ("/", "/medications", "/documents", "/settings"):
            # Start under the expanded browser bar, as the page first opens.
            await resize(cdp, width, full - CHROME_BAR["expanded"])
            await pg.goto(BASE + path)
            await pg.wait_for_selector(".bottom-tab-bar-container", timeout=20000)
            await pg.wait_for_timeout(700)

            for label, bar in (("панель браузера на месте", "expanded"), ("панель браузера спряталась", "hidden")):
                await resize(cdp, width, full - CHROME_BAR[bar])
                await pg.evaluate("() => window.scrollBy(0, window.innerHeight * 0.9)")
                await pg.wait_for_timeout(700)
                got = await pg.evaluate(READ)
                check(
                    f"{path}, {label}: полоса целиком на экране",
                    got["below"] <= 0,
                    f"низ полосы {got['barBottom']} при высоте окна {full - CHROME_BAR[bar]}, уходит за край на {got['below']} px",
                )

            # And at the very end of the page, where there is nowhere to push back to.
            await pg.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
            await pg.wait_for_timeout(800)
            got = await pg.evaluate(READ)
            check(
                f"{path}, низ страницы: полоса на месте",
                got["below"] <= 0,
                f"уходит за край на {got['below']} px, сдвиг {got['shift']}, в самом низу: {got['atEnd']}",
            )

        # Chrome's toolbar gone and the visual viewport left panned by it: the header must be at the
        # top of what a person sees, not above it under the clock.
        await pg.goto(BASE + "/")
        await pg.wait_for_timeout(700)
        await pg.evaluate(PAN, PANNED)
        await pg.wait_for_timeout(400)
        shifted = await pg.evaluate(HEADER_TOP)
        check(
            "шапка догоняет панораму Chrome и стоит на верхнем краю видимой области",
            abs(shifted) <= 2,
            f"шапка на {shifted} px от видимого верха (панорама {PANNED})",
        )
        # The spring-back at the end of a page reports a pan for a moment, and the header must not
        # chase it: it may not move before the value has settled.
        await pg.evaluate(PAN, 0)
        await pg.wait_for_timeout(120)
        await pg.evaluate(PAN, 25)
        await pg.wait_for_timeout(30)
        chase = await pg.evaluate(
            "() => getComputedStyle(document.documentElement).getPropertyValue('--vv-shift-top').trim()"
        )
        check(
            "отскок в конце страницы шапку не дёргает: сдвиг ставится только когда панорама устоялась",
            chase != "25px",
            f"сдвиг {chase}",
        )

        await ctx.close()
        await browser.close()
    summary("the bottom bar holds while Chrome resizes the page")


asyncio.run(main())
