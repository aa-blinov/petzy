"""«Значения по умолчанию» и «Типы событий»: правка не теряется молча, удаление спрашивает один раз и с числом записей."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, wait_until


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        made = []
        made_types = []
        try:
            # A run that was cut short leaves its own pet and its own types behind, and the next run then refuses to
            # create them («Это название уже есть», «Тест-М» занят). They are only ever this check's, so they go first.
            await pg.evaluate(
                """async () => {
                  const pets = (await (await fetch('/api/pets')).json()).pets;
                  for (const p of pets.filter(p => p.name === 'Тест-М')) await fetch('/api/pets/' + p._id, {method: 'DELETE'});
                  const types = (await (await fetch('/api/event-types')).json()).event_types || [];
                  for (const t of types.filter(t => !t.is_builtin && ['Т-проверка прогулка', 'Т-проверка два числа'].includes(t.label)))
                    await fetch('/api/event-types/' + t.key, {method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({with_events: true})});
                }"""
            )
            # a pet of our own, with nothing remembered for it yet
            await pg.goto(BASE + "/pets/new")
            await pg.get_by_role("button", name="Собака").click()
            await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
            await pg.get_by_role("button", name="Добавить", exact=True).click()
            await pg.get_by_role("button", name="Готово").click()
            await pg.wait_for_timeout(300)
            pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
            made.append(pid)
            await pg.evaluate("id => localStorage.setItem('selectedPetId', JSON.stringify(id))", pid)

            # nothing remembered: the header and the empty state must agree about a field with choices
            await pg.goto(BASE + "/form-defaults")
            body = await wait_until(pg, lambda t: "У обязательных полей с вариантами выбран первый вариант" in t)
            check(
                "the empty state tells the same thing as the text above it",
                "У обязательных полей с вариантами выбран первый вариант" in body
                and "У обязательного поля с вариантами, когда значение не запомнено, выбран первый вариант" in body,
                body[:240].replace(chr(10), " | "),
            )
            saved = await api(
                pg, "PUT", f"/pets/{pid}/form-defaults", {"form_defaults": {"weight": {"food": "Пакетя"}}}
            )
            check("the value was remembered for the test pet", saved["status"] == 200, str(saved["json"]))
            await pg.goto(BASE + "/form-defaults")
            check("the remembered value is on the screen", "Пакетя" in await wait_until(pg, lambda t: "Пакетя" in t))

            # the panel does not drop what was typed when the background is tapped
            await pg.get_by_text("Пакетя", exact=True).click()
            field = pg.get_by_placeholder("Значение")
            await field.wait_for(timeout=10000)
            await field.fill("Пакетя XL")
            await pg.locator(".adm-mask").click(position={"x": 195, "y": 100})
            check(
                "a tap on the background keeps the typed value instead of closing it silently",
                await pg.get_by_placeholder("Значение").count() == 1,
            )
            await pg.get_by_role("button", name="Закрыть без сохранения").click()
            dialog = await wait_until(pg, lambda t: "Введённое значение не сохранится" in t)
            check(
                "closing asks about the value that is not saved",
                "Введённое значение не сохранится" in dialog and "Остаться" in dialog,
                dialog[-200:].replace(chr(10), " | "),
            )
            await pg.get_by_role("button", name="Остаться").click()
            await pg.wait_for_timeout(300)
            check(
                "«Остаться» keeps the panel open with what was typed",
                await pg.get_by_placeholder("Значение").count() == 1
                and await pg.get_by_placeholder("Значение").input_value() == "Пакетя XL",
            )
            await pg.get_by_role("button", name="Сохранить").click()
            await field.wait_for(state="hidden", timeout=10000)
            stored = ((await api(pg, "GET", f"/pets/{pid}"))["json"].get("pet") or {}).get("form_defaults") or {}
            check("the corrected value was saved", (stored.get("weight") or {}).get("food") == "Пакетя XL", str(stored))

            # a built-in type: its number bounds are shown, its chart is said about, its icons are named in Russian
            await pg.goto(BASE + "/event-types/weight/edit")
            await wait_until(pg, lambda t: "Записи принимаются" in t)
            form = await pg.inner_text("body")
            check("the bounds of a saved number field are shown, not dropped", "Записи принимаются" in form)
            check(
                "an icon is named in Russian for a screen reader",
                await pg.get_by_role("button", name="Глаза").count() == 1,
            )
            # The demo account is not an administrator, and a built-in type may only be edited by one: the screen says
            # so instead of showing a form that would fail on save. The field-deletion checks below run on the demo's
            # own type, which it may edit.
            check(
                "a built-in type is read-only for a user who may not edit it",
                await pg.evaluate("() => !!document.querySelector('fieldset[disabled]')")
                and "Изменение увидят все" not in form,
                form[-160:].replace(chr(10), " | "),
            )
            # With another number field left the form names the loss instead: the chart is waiting for a choice.
            walk_key = (
                await api(
                    pg,
                    "POST",
                    "/event-types",
                    {
                        "label": "Т-проверка два числа",
                        "icon": "footprints",
                        "color": "green",
                        "fields": [
                            {"name": "first", "label": "Первое", "type": "number", "required": False},
                            {"name": "second", "label": "Второе", "type": "number", "required": False},
                        ],
                        "chart": {"kind": "value", "value_field": "first", "value_label": "Первое"},
                    },
                )
            )["json"]["key"]
            made_types.append(walk_key)
            await pg.goto(BASE + f"/event-types/{walk_key}/edit")
            await pg.get_by_role("button", name="Удалить поле").first.wait_for(timeout=10000)
            await pg.get_by_role("button", name="Удалить поле").first.click()
            body = await wait_until(pg, lambda t: "Поле для графика ушло" in t)
            check(
                "with another number left it says the chart field is gone and asks for another",
                "Поле для графика ушло" in body,
                body[-160:].replace(chr(10), " | "),
            )
            await pg.screenshot(path="defaults_chart.png")

            # one question about deleting a type, with the number of records in it
            walk_type = (
                await api(
                    pg,
                    "POST",
                    "/event-types",
                    {"label": "Т-проверка прогулка", "icon": "paw", "color": "green", "fields": []},
                )
            )["json"]["key"]
            made_types.append(walk_type)
            record = await api(
                pg,
                "POST",
                f"/events?pet_id={pid}",
                {"pet_id": pid, "type": walk_type, "date": "2026-10-01", "time": "09:00", "fields": {}},
            )
            check("the record for the count is written", record["status"] == 201, str(record)[:160])
            await pg.goto(BASE + "/event-types")
            await pg.get_by_role("button", name="Удалить Т-проверка прогулка").wait_for(timeout=10000)
            await pg.get_by_role("button", name="Удалить Т-проверка прогулка").click()
            dialog = await wait_until(pg, lambda t: "У типа 1 запись" in t)
            check(
                "the first question already says how many records go with the type",
                "У типа 1 запись" in dialog and "Удалить тип и записи" in dialog,
                dialog[-220:].replace(chr(10), " | "),
            )
            # The dialog's actions are divs, as in every dialog of the app (see check_settings_links.py)
            await pg.locator(".adm-dialog-button", has_text="Удалить тип и записи").last.click()
            await pg.wait_for_timeout(1800)
            left = (await api(pg, "GET", "/event-types"))["json"]["event_types"]
            check("the type and its record are gone", not any(t["key"] == walk_type for t in left))
            made_types.remove(walk_type)
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            for key in made_types:
                await api(pg, "DELETE", f"/event-types/{key}?with_events=true")
            for pid in made:
                await api(pg, "DELETE", f"/pets/{pid}")
        return summary("defaults and event types")


asyncio.run(main())
