"""What the e2e checks share: a phone-sized browser, a sign-in as the demo owner, the API from inside the page, and PASS/FAIL lines."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from playwright.async_api import async_playwright  # noqa: F401  (re-exported to the checks)
from seed_demo import DEMO_PASSWORD  # the demo account of the local stack

BASE = os.environ.get("PETZY_E2E_BASE", "http://localhost:3000")
_fails = []


async def new_page(browser, dark=False, width=390, height=844, sw=True):
    ctx = await browser.new_context(
        viewport={"width": width, "height": height},
        has_touch=True,
        is_mobile=True,
        locale="ru-RU",
        color_scheme="dark" if dark else "light",
        service_workers="allow" if sw else "block",
    )
    pg = await ctx.new_page()
    return ctx, pg


async def login(pg, user="demo", pet_prefix="Рекс"):
    await pg.goto(BASE + "/login")
    await pg.get_by_placeholder("Введите логин").fill(user)
    await pg.get_by_placeholder("Введите пароль").fill(DEMO_PASSWORD)
    await pg.get_by_role("button", name="Войти").click()
    await pg.wait_for_url(lambda u: "/login" not in u, timeout=20000)
    await pg.wait_for_timeout(1500)
    pets = await pg.evaluate("fetch('/api/pets').then(r => r.json()).then(d => d.pets.map(p => [p.name, p._id]))")
    return next(i for n, i in pets if n.startswith(pet_prefix))


async def api(pg, method, path, body=None):
    return await pg.evaluate(
        """async ([m, p, b]) => { const r = await fetch('/api' + p, {method: m, credentials: 'include', headers: b ? {'Content-Type': 'application/json'} : {}, body: b ? JSON.stringify(b) : undefined});
        let j = null; try { j = await r.json(); } catch (e) {} return {status: r.status, json: j}; }""",
        [method, path, body],
    )


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def summary(title):
    print(f"== {title}: " + ("ALL PASS" if not _fails else f"{len(_fails)} FAILED"))


async def swipe_wheel(pg, ctx, column, items, up=True):
    """Turn a wheel of antd Picker by touch, as a finger does: `items` items up (or down)."""
    cdp = await ctx.new_cdp_session(pg)
    wheel = pg.locator(".adm-picker-view-column-wheel").nth(column)
    box = await wheel.bounding_box()
    h = (await pg.locator(".adm-picker-view-column-item").first.bounding_box())["height"]
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    sign = -1 if up else 1
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    steps = 10
    for i in range(1, steps + 1):
        await cdp.send(
            "Input.dispatchTouchEvent",
            {"type": "touchMove", "touchPoints": [{"x": x, "y": y + sign * i * items * h / steps}]},
        )
        await pg.wait_for_timeout(16)
    await pg.wait_for_timeout(250)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await pg.wait_for_timeout(900)
