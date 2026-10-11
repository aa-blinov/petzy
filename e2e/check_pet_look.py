"""A pet's colour is that pet's, not the app's.

The look used to be put on <body>, and everything under it read the same two
tokens, so a pet with a sage coat turned the chips, the segmented switches,
the dose widget and the FAB green. The card and the pet's chip in the switcher
already carry the colour themselves, so removing it from <body> is the whole
fix: nothing about the controls changes, and the pet keeps its coat.

The scene stays app-wide on purpose: it is the background of every screen.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

READ = """
() => {
  const root = getComputedStyle(document.documentElement);
  const body = getComputedStyle(document.body);
  const card = document.querySelector('[data-pet-accent]');
  const pill = document.querySelector('.app-tab-bar__item--active .app-tab-bar__icon');
  return {
    brand: root.getPropertyValue('--app-accent-soft').trim(),
    onBody: body.getPropertyValue('--app-accent-soft').trim(),
    bodyCarriesThePet: document.body.hasAttribute('data-pet-accent'),
    onCard: card ? getComputedStyle(card).getPropertyValue('--app-accent-soft').trim() : null,
    pill: pill ? getComputedStyle(pill, '::before').backgroundColor : null,
    scene: body.getPropertyValue('--pet-scene-bg').trim(),
  };
}
"""


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx, pg = await new_page(browser)
        await login(pg, "demo", "Рекс")

        for path in ("/", "/medications", "/documents", "/settings"):
            await pg.goto(BASE + path)
            await pg.wait_for_selector(".app-tab-bar__item--active", timeout=20000)
            await pg.wait_for_timeout(800)
            got = await pg.evaluate(READ)

            check(
                f"{path}: тема питомца не перекрашивает всё подряд",
                got["onBody"] == got["brand"] and not got["bodyCarriesThePet"],
                f"в :root {got['brand']}, в body {got['onBody']}, атрибут на body: {got['bodyCarriesThePet']}",
            )
            check(
                f"{path}: подложка активной вкладки фирменная, не питомца",
                got["pill"] not in (None, got["onCard"]),
                f"подложка {got['pill']}, цвет питомца {got['onCard']}",
            )

        # And the pet itself still wears its colour where the card is drawn.
        await pg.goto(BASE + "/")
        await pg.wait_for_selector("[data-pet-accent]", state="attached", timeout=20000)
        await pg.wait_for_timeout(800)
        got = await pg.evaluate(READ)
        check(
            "карточка питомца по-прежнему в его собственном цвете",
            got["onCard"] is not None and got["onCard"] != got["brand"],
            f"в карточке {got['onCard']}, фирменный {got['brand']}",
        )

        await ctx.close()
        await browser.close()
    summary("a pet's colour stays on the pet")


asyncio.run(main())
