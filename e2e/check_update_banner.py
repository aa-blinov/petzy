"""A new release offers «Обновить»; a picture shown before is shown again at once.

The app used to take a new release by reloading itself on the next main tab, and an installed app on a phone needed
reinstalling to be sure. Now a release that takes over while the app is open shows «Вышла новая версия Petzy» with
«Обновить», and the tap loads it. A new service worker cannot be released from a check, so the event the app
listens for is fired by hand once the page is under a worker.

Pictures: the browser keeps them, but every screen drew them again from a blurred placeholder with a fade, which looked
like loading anew each time. Coming back to the feed, the pet's photo is there at once.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary, settle

PHOTO = """(() => {
  const imgs = [...document.querySelectorAll('img')].filter(i => i.src.includes('/api/pets/') && i.src.includes('/photo'));
  const placeholder = imgs.some(i => /[?&]w=20(&|$)/.test(i.src));
  const main = imgs.find(i => !/[?&]w=20(&|$)/.test(i.src));
  return { placeholder, opacity: main ? getComputedStyle(main).opacity : null };
})()"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        await login(pg)
        await pg.goto(BASE + "/")
        await settle(pg)
        # Back to the feed through the app: the photo was seen, so no placeholder and no fade this time.
        await pg.get_by_text("Лекарства", exact=True).last.click()
        await settle(pg, 150)
        await pg.get_by_text("Лента", exact=True).last.click()
        await settle(pg, 150)
        got = await pg.evaluate(PHOTO)
        check(
            "a photo seen before shows at once, without the blurred placeholder", got["placeholder"] is False, str(got)
        )
        check("and without fading in again", got["opacity"] == "1", str(got))

        # Under a service worker, so the page counts as one that had a worker before the release.
        await pg.reload()
        await settle(pg)
        controlled = await pg.evaluate("!!navigator.serviceWorker.controller")
        check("the page is under the service worker", controlled)
        check("no offer before a release", await pg.get_by_text("Вышла новая версия").count() == 0)
        await pg.evaluate("navigator.serviceWorker.dispatchEvent(new Event('controllerchange'))")
        await pg.wait_for_timeout(400)
        check(
            "a release that takes over offers «Обновить»", await pg.get_by_text("Вышла новая версия Petzy").count() == 1
        )
        async with pg.expect_navigation(timeout=10000):
            await pg.get_by_role("button", name="Обновить").click()
        await settle(pg, 150)
        check(
            "«Обновить» loads the release, and the offer is gone",
            await pg.get_by_text("Вышла новая версия").count() == 0,
        )
        await ctx.close()
        await browser.close()
    summary("new release and pictures seen before")


asyncio.run(main())
