"""The numbers for a phone that shows the fault: `?diag=1`.

A headless browser never pans the visual viewport and never shows a keyboard, so the fault a person
sees on an iPhone cannot be reproduced here. The overlay is how it gets measured instead: it reads
the visual viewport's height and pan, the page's own height and scroll, the two shifts the bars use
and whether the app thinks a keyboard is up. It must appear only when asked, and it must survive a
route change — the moment worth reading is on the form, not on the page the address was typed on.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, settle, summary  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(browser, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        try:
            await pg.goto(BASE + "/")
            await settle(pg)
            await pg.wait_for_timeout(600)
            check(
                "без просьбы плашки нет",
                await pg.locator(".diag").count() == 0,
            )

            await pg.goto(BASE + "/?diag=1")
            await settle(pg)
            await pg.wait_for_timeout(700)
            shown = await pg.locator(".diag").inner_text()
            check(
                "по ?diag=1 плашка показывает цифры полос",
                all(word in shown for word in ("vv", "top", "shift", "kb", "hdr", "bar")),
                shown.replace("\n", " | "),
            )

            # The query string is gone on the next route; the overlay has to stay.
            await pg.locator(".app-fab").click()
            await settle(pg, 200)
            await pg.wait_for_timeout(400)
            await pg.get_by_role("button", name="Дефекация").first.click()
            await settle(pg, 300)
            await pg.wait_for_timeout(700)
            check(
                "переход в форму плашку не теряет: читать надо именно там",
                "/form/defecation" in pg.url and await pg.locator(".diag").is_visible(),
                pg.url.replace(BASE, ""),
            )
        finally:
            await pg.evaluate("() => sessionStorage.removeItem('petzy:diag')")
            await ctx.close()
            await browser.close()
    summary("цифры полос для диагностики")


asyncio.run(main())
