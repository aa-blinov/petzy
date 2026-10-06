"""Черновик формы принадлежит своему питомцу, а старый черновик переезжает сам.

Два питомца открывают одну и ту же форму. Набранное для одного не должно
оказываться в форме другого. Черновик пишется при истечении сессии, поэтому
проверка роняет сессию сама, а потом смотрит, кому вернулось набранное.

Вторая часть проверки про переезд: черновик, записанный прежней версией
(одна запись по пути экрана, без питомца), должен вернуться на свой экран сам,
как только откроется форма, — иначе человек потеряет недописанное при выкатке.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def _write_draft(pg, pet_id: str, weight: str) -> None:
    """Fill the weight form for a pet and drop the session, as an expiry does."""
    await pg.evaluate(
        "id => { localStorage.setItem('selectedPetId', JSON.stringify(id)); }",
        pet_id,
    )
    await pg.goto(BASE + "/form/weight")
    await pg.wait_for_timeout(2000)
    await pg.get_by_label("Вес (кг)").fill(weight)
    await pg.wait_for_timeout(600)
    # Сессия кончилась: следующий запрос получит 401, и приложение спрячет черновик.
    await pg.context.clear_cookies()
    await pg.get_by_role("button", name="Создать").click()
    await pg.wait_for_url(lambda u: "/login" in u, timeout=20000)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        made = []
        try:
            await login(pg, "demo", "Рекс")
            # Свой питомец и второй, чтобы было видно, чей это черновик.
            for name in ("Тест-М", "Тест-К"):
                r = await api(pg, "POST", "/pets", {"name": name, "species": "собака"})
                made.append(r["json"]["pet"]["_id"])
            mine, other = made
            check("two scratch pets are made", bool(mine and other), str(made))

            # Два черновика от двух питомцев: если хранилище держит только один, второй затёр первый,
            # и это видно здесь — первому питомцу досталось бы чужое число.
            await _write_draft(pg, mine, "12,4")
            await login(pg, "demo", "Рекс")
            await _write_draft(pg, other, "9,9")
            await login(pg, "demo", "Рекс")

            for pet_id, weight, who in ((mine, "12,4", "the first pet"), (other, "9,9", "the second pet")):
                await pg.evaluate("id => localStorage.setItem('selectedPetId', JSON.stringify(id))", pet_id)
                await pg.goto(BASE + "/form/weight")
                await pg.wait_for_timeout(2200)
                value = await pg.get_by_label("Вес (кг)").input_value()
                check(f"{who} gets its own typing back", value == weight, repr(value))
                check(
                    f"{who} is told their typing came back",
                    "Вернули то, что вы вводили" in await pg.inner_text("body"),
                )

            # Черновик прежней версии переезжает сам, без всякого приглашения.
            await pg.evaluate(
                """() => {
                  sessionStorage.setItem(
                    'petzy:sessionDraft',
                    JSON.stringify({ path: '/form/weight', values: { date: '2026-10-06', time: '10:00', weight: '9,9' } }),
                  );
                }"""
            )
            await pg.evaluate("id => localStorage.setItem('selectedPetId', JSON.stringify(id))", mine)
            await pg.goto(BASE + "/form/weight")
            await pg.wait_for_timeout(2200)
            adopted = await pg.get_by_label("Вес (кг)").input_value()
            check(
                "a draft of the previous version is adopted by its own screen",
                adopted == "9,9",
                repr(adopted),
            )
            check(
                "and the old entry is gone, so it cannot come back twice",
                await pg.evaluate("() => !sessionStorage.getItem('petzy:sessionDraft')"),
            )
        finally:
            for pet_id in made:
                await api(pg, "DELETE", f"/pets/{pet_id}")
        await b.close()
    return summary("a form's draft belongs to its pet")


asyncio.run(main())
