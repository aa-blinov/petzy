"""«Потянуть для обновления» на всех пяти вкладках, а не только на ленте.

Жест был на ленте, в лекарствах (и то лишь когда список не пуст) и в документах, а на медкарте и
в настройках его не было вовсе: человек тянул вниз, и ничего не происходило. Теперь это одна
общая деталь (components/AppPullToRefresh), и она стоит на каждом экране-вкладке, пустом тоже.

Проверяется и то, что жест действительно тянет данные: на «Настройках» считается запрос
аккаунта до протяжки и после, и он должен пойти заново.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary, settle  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

TABS = [
    ("Лента", "/"),
    ("Лекарства", "/medications"),
    ("Медкарта", "/medical-card"),
    ("Документы", "/documents"),
    ("Настройки", "/settings"),
]


async def pull(pg) -> bool:
    """Протянуть вниз по обёртке настоящим касанием: antd-mobile слушает только touch-указатели."""
    box = await pg.locator(".adm-pull-to-refresh").first.bounding_box()
    if not box:
        return False
    x = box["x"] + box["width"] / 2
    y = box["y"] + 40
    cdp = await pg.context.new_cdp_session(pg)

    def at(ty: float) -> dict:
        return {"touchPoints": [{"x": x, "y": ty}]}

    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", **at(y)})
    for step in (40, 90, 140, 190, 230):
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", **at(y + step)})
        await pg.wait_for_timeout(40)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    return True


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(browser, width=390, height=844, sw=False)
        rex = await login(pg, "demo", "Рекс")
        try:
            have = []
            for name, path in TABS:
                await pg.goto(BASE + path)
                await settle(pg)
                await pg.wait_for_timeout(700)
                have.append((name, await pg.locator(".adm-pull-to-refresh").count()))
            check(
                "каждая вкладка отвечает на протяжку вниз одним и тем же жестом",
                all(count >= 1 for _, count in have),
                str(have),
            )

            # На «Настройках» жеста не было вовсе: он и показывает, что жест тянет данные.
            await pg.goto(BASE + "/settings")
            await settle(pg)
            await pg.wait_for_timeout(900)
            account: list[str] = []
            pg.on("request", lambda r: account.append(r.url) if "/me/account" in r.url else None)
            before = len(account)
            pulled = await pull(pg)
            await pg.wait_for_timeout(1200)
            check(
                "протяжка на «Настройках» перезапрашивает аккаунт",
                pulled and len(account) > before,
                f"протяжка: {pulled}, запросов: {len(account) - before}",
            )
            check(
                "после обновления экран на месте и без ошибки",
                "Настройки" in await pg.inner_text("body"),
            )

            # Медкарта собирается на сервере заново на каждый запрос, поэтому жест здесь и есть
            # обновление: врач мог дописать запись с другого устройства.
            await pg.goto(BASE + f"/pets/{rex}/medical-card")
            await settle(pg)
            await pg.wait_for_timeout(900)
            card: list[str] = []
            pg.on("request", lambda r: card.append(r.url) if "/medical-card" in r.url else None)
            before = len(card)
            pulled = await pull(pg)
            await pg.wait_for_timeout(1400)
            check(
                "протяжка на «Медкарте» перезапрашивает карту с сервера",
                pulled and len(card) > before,
                f"протяжка: {pulled}, запросов: {len(card) - before}",
            )
        finally:
            await ctx.close()
            await browser.close()
    summary("протяжка вниз на всех вкладках")


asyncio.run(main())
