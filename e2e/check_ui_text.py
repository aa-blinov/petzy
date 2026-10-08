"""Слова в интерфейсе без служебных знаков: ни «|», ни «·», ни «—».

Правило владельца: два факта в одной строке разделяются раскладкой или запятой, а не
знаком. На разборе нашлась прямая палочка между силой препарата и дозой, а «·» уже
запрещённый знак. Ниже — проверка, чтобы такое не вернулось ни на одном экране.

Документы (справка, политика, согласие) и адреса проверка не читает: там обычная
пунктуация, а в адресе может быть дефис. Проходится по экранам с данными, где текста
больше всего.

Нужны локальный стенд и демо-данные.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, wait_until

PET = "Тест-М"
BANNED = {"·": "средняя точка", "|": "палочка", "—": "длинное тире", "–": "короткое тире"}

# Знак, который сам по себе ничего не значит в интерфейсе: склеенные два факта видно
# и без него, а рядом с числом он читается как часть числа.
PAGE_TEXT = """() => {
  const main = document.querySelector('main');
  if (!main) return [];
  return [...new Set(main.innerText.split('\\n').map((s) => s.trim()).filter(Boolean))];
}"""


async def look(pg, url: str, ready: str) -> list[str]:
    await pg.goto(url)
    await wait_until(pg, lambda t: ready in t, timeout=15_000)
    await pg.wait_for_timeout(600)
    return await pg.evaluate(PAGE_TEXT)


async def main() -> None:
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        made = await api(pg, "POST", "/pets", {"name": PET, "species": "собака", "birth_date": "2020-01-01"})
        pid = made["json"]["pet"]["_id"]
        try:
            await api(
                pg,
                "POST",
                "/medical-records",
                {"pet_id": pid, "date": "2026-05-29", "kind": "vaccination", "title": "Нобивак DHPPi"},
            )
            await api(
                pg,
                "POST",
                "/medications",
                {
                    "pet_id": pid,
                    "name": "Тест-лекарство",
                    "dosage": "1 таблетка",
                    "strength": "1,5 мг/мл",
                    "default_dose": 2.5,
                    "dose_unit": "мл",
                },
            )
            await api(pg, "POST", "/documents", {"pet_id": pid, "title": "Тест-документ", "category": "analysis"})

            screens = [
                ("лента", "/", "Лента"),
                ("история", "/history", "История"),
                ("питомцы", "/pets", "Мои питомцы"),
                ("лекарства", "/medications", "Тест-лекарство"),
                ("документы", "/documents", "Тест-документ"),
                ("медкарта", f"/pets/{pid}/medical-card", "Медкарта"),
                ("профилактика", f"/pets/{pid}/medical-card/prevention", "Прививки"),
                ("визиты", f"/pets/{pid}/medical-card/visits", "Визиты"),
                ("данные для врача", f"/pets/{pid}/medical-profile", "Данные для врача"),
                ("к приёму", f"/pets/{pid}/visit-prep", "К приёму"),
                ("настройки", "/settings", "Настройки"),
                ("почта", "/settings/email", "Почта"),
                ("пароль", "/settings/password", "Текущий пароль"),
                ("значения по умолчанию", "/form-defaults", "Значения по умолчанию"),
                ("события питомца", "/pet-events", "События питомца"),
                ("оформление", "/pet-look", "Подложка"),
                ("типы событий", "/event-types", "Типы событий"),
                ("новый тип события", "/event-types/new", "Поля"),
            ]
            for name, path, ready in screens:
                lines = await look(pg, BASE + path, ready)
                found = [(line, glyph) for line in lines for glyph in BANNED if glyph in line]
                check(
                    f"«{name}»: служебных знаков нет",
                    not found,
                    "; ".join(f"{BANNED[g]} в «{line[:50]}»" for line, g in found[:3]),
                )
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()

    summary("знаки в словах интерфейса")


asyncio.run(main())
