"""Типы событий: список говорит, что он не про встроенные типы, строка типа названа, а пустой экран не зовёт
создать тип дважды (создание доступно в пустом состоянии, в списке — одна кнопка)."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

LABEL = "Тип для проверки"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        key = None
        try:
            created = await api(
                pg,
                "POST",
                "/event-types",
                {"label": LABEL, "icon": "paw", "color": "blue", "fields": [], "chart": {"kind": "count"}},
            )
            key = created["json"].get("key")
            await pg.goto(BASE + "/event-types")
            await pg.wait_for_timeout(1500)
            body = await pg.inner_text("body")
            check(
                "в списке сказано, что встроенных типов здесь нет",
                "Встроенных типов здесь нет" in body,
                body[:220].replace(chr(10), " | "),
            )
            check(
                "и что добавляются они в «События питомца»",
                "События питомца" in body,
            )
            # Строка типа называла себя только точкой «›»: ни названия, ни слова о том, что она открывает.
            check(
                "строка типа называет себя и говорит, что открывает правку",
                await pg.get_by_role("button", name=f"Изменить тип {LABEL}").count() == 1,
            )
            check(
                "кнопка создания на экране одна",
                await pg.get_by_role("button", name="Создать тип события").count() == 1,
            )
            check(
                "в списке нет точек-разделителей",
                "·" not in body,
            )

            # Правка чужого типа: чужая форма открывается целиком, а отказ приходит только на сохранении.
            # Встроенный тип demo не администратор, поэтому править его нельзя.
            await pg.goto(BASE + "/event-types/weight/edit")
            await pg.wait_for_timeout(1500)
            form = await pg.inner_text("body")
            check("сказано, что встроенный тип меняет администратор", "меняет его администратор" in form)
            check(
                "у чужого типа нет кнопки сохранения",
                await pg.get_by_role("button", name="Сохранить", exact=True).count() == 0,
                form[:220].replace(chr(10), " | "),
            )
            check(
                "но поля показаны для чтения",
                "Записи принимаются" in form,
            )
            check(
                "нет горизонтальной прокрутки",
                await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0,
            )
        finally:
            if key:
                await api(pg, "DELETE", f"/event-types/{key}")
            await ctx.close()
        await b.close()
    summary("event types list")


asyncio.run(main())
