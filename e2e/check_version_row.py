"""Settings say which build is on the phone and which one the server runs.

Both numbers come from the deploy (the commit it built), so a bug report and a release say the same thing. The local
stand is not deployed by the workflow and says so instead of inventing a commit.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        await login(pg)
        await pg.goto(BASE + "/settings")
        await pg.wait_for_timeout(1800)
        body = await pg.inner_text("body")
        check("«О приложении» has a «Версия» row", "Версия" in body)
        line = next((ln for ln in body.split("\n") if ln.startswith("Приложение")), "")
        check("it names the build on the phone", line.startswith("Приложение"), line)
        check("and the one the server runs", "сервер" in line, line)
        await ctx.close()
        await browser.close()
    summary("version in settings")


asyncio.run(main())
