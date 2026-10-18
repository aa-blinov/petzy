"""A session that ends on a form brings the person back to that form, with its pet, after the sign-in.

The sign-in screen promises «Войдите, и вы вернётесь на тот же экран, где были». The pet choice was
wiped with the session, so a form for a pet landed on the feed instead, and what was typed did not
come back with it. The same login gets its pet and its place back; another login gets neither.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary, settle


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx, pg = await new_page(browser, width=390, height=844)
        await login(pg, "demo", "Рекс")
        await pg.goto(BASE + "/form/weight")
        await settle(pg)
        await pg.get_by_label("Вес (кг)").fill("9,9")
        await pg.wait_for_timeout(300)
        await ctx.clear_cookies()
        await pg.get_by_role("button", name="Создать").click()
        await settle(pg, 150)
        check("the session that ended sends the person to the sign-in screen", "/login" in pg.url, pg.url)
        await pg.get_by_placeholder("Введите логин").fill("demo")
        from common import DEMO_PASSWORD

        await pg.get_by_placeholder("Введите пароль").fill(DEMO_PASSWORD)
        await pg.get_by_role("button", name="Войти").click()
        await pg.wait_for_url(lambda u: "/form/weight" in u, timeout=10000)
        await pg.get_by_label("Вес (кг)").wait_for(timeout=8000)
        check("after the sign-in the person is back on that form", "/form/weight" in pg.url, pg.url)
        value = await pg.evaluate(
            "document.querySelector('input#weight') ? document.querySelector('input#weight').value : null"
        )
        check(
            "and the value typed before is there",
            value is not None and value.replace(".", ",") == "9,9",
            f"в поле «{value}»",
        )
        await ctx.close()
        await browser.close()
    summary("a session that ended brings the person back to their form")


asyncio.run(main())
