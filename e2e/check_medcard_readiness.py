"""Готовность к приёму: шкала, дверь под ней и день замера в скобках.

- шкала — это измеритель, а не список: чем больше заполнено, тем больше точек горит слева, и
  горит первая точка, а не та, чей пункт случайно заполнили (у веса пункт последний в списке, и
  раньше при «1 из 5» зажигалась именно последняя точка);
- дверь подсказки стоит в своей строке и отделена от текста волосяной линейкой, как строки на
  других вкладках;
- день замера стоит в скобках через пробел от числа: «12,4 кг (20.10.2026)».

Питомец свой («Готовность-М»), удаляется в конце; демо-питомец только читается.
"""

import asyncio
import re

from common import BASE, async_playwright, check, login, new_page, summary, settle

MUTED = "rgb(229, 223, 208)"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        pid = None
        try:
            # Питомец без записей, потом один вес: это последний пункт готовности в списке.
            made = await pg.evaluate(
                """async () => {
                    const r = await fetch('/api/pets', {method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({name: 'Готовность-М', species: 'dog', breed: 'Лабрадор',
                            gender: 'male', birth_date: '2024-05-01'})});
                    const d = await r.json();
                    return d.pet || d;
                }"""
            )
            pid = made.get("_id") or made.get("id")

            await pg.goto(BASE + f"/form/weight?pet={pid}")
            await settle(pg, 200)
            await pg.get_by_label("Вес (кг)").fill("12,4")
            await pg.get_by_role("button", name="Создать").click()
            await settle(pg, 300)
            await pg.wait_for_timeout(600)

            await pg.goto(BASE + f"/pets/{pid}/medical-card")
            await settle(pg)
            await pg.wait_for_timeout(900)

            got = await pg.evaluate(
                """(muted) => {
                    const block = document.querySelector('.medcard__ready');
                    const dots = [...block.querySelectorAll('.medcard__ready-dot')];
                    const row = block.querySelector('.medcard__ready-action-row');
                    const weight = document.querySelector('.medcard__weight-chip');
                    return {
                        count: block.querySelector('.medcard__ready-count').innerText.replace(/\\n/g, ' '),
                        meter: dots.map((d) => (getComputedStyle(d).backgroundColor === muted ? '.' : 'X')).join(''),
                        row: row !== null,
                        line: row ? getComputedStyle(row).borderTopWidth : 'нет',
                        weight: weight ? weight.innerText.replace(/\\n/g, ' ') : 'нет веса',
                    };
                }""",
                MUTED,
            )

            check(
                "готовность считает, сколько из пяти заполнено",
                "1 из 5" in got["count"],
                got["count"],
            )
            check(
                "шкала зажигает точки слева: при «1 из 5» горит первая, а не та, чей пункт заполнили",
                got["meter"] == "X....",
                got["meter"],
            )
            check(
                "дверь подсказки стоит своей строкой под волосяной линейкой, как на других вкладках",
                got["row"] and got["line"] == "1px",
                f"строка: {got['row']}, линейка: {got['line']}",
            )
            check(
                "день замера стоит в скобках через пробел от числа",
                re.search(r"\d кг \(", got["weight"]) is not None,
                got["weight"],
            )
        finally:
            if pid:
                await pg.evaluate("async (id) => { await fetch('/api/pets/' + id, {method: 'DELETE'}); }", pid)
            await ctx.close()
            await b.close()
    summary("готовность к приёму: шкала, дверь и скобки")


asyncio.run(main())
