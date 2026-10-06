"""Пути по приложению: каждый экран со своими словами и без сбоя.

Обход идёт по всем маршрутам с питомцем, у которого есть записи всех видов, лекарство с
приёмом и документ: пустой список показывает одно и то же почти на всех экранах, и по
нему не видно, что данные вообще рисуются. На каждом экране проверяется своё слово,
отсутствие текста о сбое и отсутствие горизонтальной прокрутки.

Свой питомец, записи, лекарство и документ делает проверка сама и убирает за собой.
"""

import asyncio
import json

from common import BASE, api, async_playwright, check, login, new_page, summary, wait_until

PET = "Тест-М"

# Маршрут: слово, без которого экран не тот. Порядок такой же, как в App.tsx.
SCREENS = [
    ("/", ["Лента", "Рекс"]),
    ("/medical-card", ["Медкарта", "Записи"]),
    ("/history", ["История", "Экспорт"]),
    ("/pets", ["Мои питомцы", PET]),
    ("/pets/new", ["Добавить питомца", "Вид питомца"]),
    ("@pet/edit", ["Редактировать питомца", "Порода", "Дата рождения"]),
    ("@pet/medical-card", ["Медкарта", "Заполнено"]),
    ("@pet/medical-card/prevention", ["Прививки", "Нобивак DHPPi"]),
    ("@pet/medical-card/visits", ["Визиты и операции", "Осмотр"]),
    ("@pet/medical-card/life", ["Питание и условия"]),
    ("@pet/medical-profile", ["Данные для врача", "Аллергий нет"]),
    ("@pet/visit-prep", ["К приёму", "Что беспокоит"]),
    ("@pet/medical-records/new", ["Не выбрано, что записать"]),
    ("@record", ["Название вакцины", "Нобивак DHPPi"]),
    ("/form/weight", ["Записать: Вес"]),
    ("@event", ["правка", "Питомец"]),
    ("/medications", ["Тест-лекарство", "Ежедневно в 09:00"]),
    ("/medications/new", ["Новое лекарство", "На упаковке"]),
    ("@med/edit", ["Изменить лекарство", "Тест-лекарство"]),
    ("/documents", ["Документы", "Тест-документ"]),
    ("/documents/new", ["Новый документ", "Категория"]),
    ("@doc/edit", ["Редактировать документ", "п.pdf", "Анализы"]),
    ("/settings", ["Настройки", "Мои питомцы"]),
    ("/settings/medical-links", ["Ссылки на медкарту"]),
    ("/settings/email", ["Почта", "Адрес почты"]),
    ("/settings/password", ["Пароль", "Текущий пароль"]),
    ("/settings/delete-account", ["Удаление аккаунта", "Удалятся"]),
    ("/pet-look", ["Оформление питомца", "Подложка"]),
    ("/form-defaults", ["Значения по умолчанию"]),
    ("/pet-events", ["События питомца"]),
    ("/tiles-settings", ["События питомца"]),
    ("/help", ["Справка", "Частые вопросы"]),
    ("/event-types", ["Типы событий"]),
    ("/event-types/new", ["Новый тип события", "Поля"]),
    ("/event-types/weight/edit", ["Редактировать тип", "Встроенный тип"]),
    ("/users/demo", ["Общие питомцы"]),
    ("/admin", ["права администратора"]),
    ("@share", ["Скачать PDF", "Ссылка действует до"]),
]

# Экраны, где видно, что сломалось: не «пусто», а именно отказ или сбой.
BROKEN = ["Не удалось загрузить", "Что-то пошло не так", "Ошибка соединения", "Сервер не ответил"]


async def open_screen(pg, path):
    """Открыть адрес. Обход делает сорок переходов подряд, и один из них изредка обрывается:
    это сеть, а не экран, поэтому переход повторяется."""
    for attempt in (1, 2, 3):
        try:
            await pg.goto(BASE + path)
            return True
        except Exception:
            await pg.wait_for_timeout(600)
    return False


async def fits_screen(pg):
    """Уходит ли страница вбок. None, если страница ушла из-под вопроса: это не про ширину."""
    for _ in range(4):
        try:
            return not await pg.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 1")
        except Exception:
            # Часть адресов переводит на другой экран сразу, и страница в этот момент ещё
            # переезжает. Это не про ширину, поэтому спрашиваем ещё раз.
            await pg.wait_for_timeout(400)
    return None


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        pid = record = med = doc = token = event = None
        try:
            await login(pg, "demo", "Рекс")
            pets = (await api(pg, "GET", "/pets"))["json"]["pets"]
            for leftover in [q for q in pets if q["name"] == PET]:
                await api(pg, "DELETE", f"/pets/{leftover['_id']}")
            pid = (await api(pg, "POST", "/pets", {"name": PET, "species": "собака"}))["json"]["pet"]["_id"]
            await api(pg, "PUT", f"/pets/{pid}/look", {"accent": "teal", "scene": "dots", "backdrop": "fill"})
            # До каждой навигации, а не один раз: иначе запись приходится в момент перехода
            # и страница успевает уехать.
            await pg.add_init_script(f"localStorage.setItem('selectedPetId', JSON.stringify({json.dumps(pid)}))")

            for body in (
                {"kind": "vaccination", "title": "Нобивак DHPPi", "protects": "dhpp", "next_due": "2027-10-05"},
                {"kind": "parasite", "title": "Бравекто", "target": "fleas_ticks"},
                {"kind": "visit", "title": "Осмотр", "clinic": "Ветклиника", "vet": "Ирина"},
                {"kind": "procedure", "title": "Чистка зубов", "clinic": "Ветклиника"},
            ):
                made = await api(pg, "POST", "/medical-records", {"pet_id": pid, "date": "2026-10-05", **body})
                if body["kind"] == "vaccination" and made["status"] == 201:
                    record = made["json"]["id"]
            noted = await api(
                pg,
                "POST",
                "/events",
                {"pet_id": pid, "date": "2026-10-05", "time": "10:00", "type": "weight", "fields": {"weight": 12.4}},
            )
            if noted["status"] == 201:
                event = noted["json"].get("id")
            course = await api(
                pg,
                "POST",
                "/medications",
                {
                    "pet_id": pid,
                    "name": "Тест-лекарство",
                    "type": "Таблетка",
                    "form_factor": "tablet",
                    "strength": "50 мг",
                    "dose_unit": "таб",
                    "default_dose": 1,
                    "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["09:00"]},
                },
            )
            if course["status"] == 201:
                med = course["json"].get("id") or course["json"].get("_id")
            # Документ не создаётся без файла, поэтому он уходит тем же multipart, каким
            # уходит из формы.
            paper = await pg.evaluate(
                """async ([pid]) => {
                    const fd = new FormData();
                    fd.append('pet_id', pid);
                    fd.append('category', 'lab_result');
                    fd.append('title', 'Тест-документ');
                    fd.append('file', new File([new Uint8Array([37, 80, 68, 70, 45, 49, 46, 52])], 'п.pdf', { type: 'application/pdf' }));
                    const r = await fetch('/api/documents', { method: 'POST', body: fd, credentials: 'include' });
                    let j = null; try { j = await r.json(); } catch (e) {}
                    return { status: r.status, json: j };
                }""",
                [pid],
            )
            listed = (await api(pg, "GET", f"/documents?pet_id={pid}"))["json"].get("documents") or []
            doc = listed[0]["_id"] if listed else None
            shared = await api(pg, "POST", f"/pets/{pid}/medical-card/shares", {})
            token = (shared.get("json") or {}).get("token") or (shared.get("json") or {}).get("share", {}).get("token")

            check(
                "данные для обхода созданы",
                bool(pid and record and med and doc and token and event),
                f"питомец {pid}, запись {record}, лекарство {med}, документ {doc}, "
                f"ответ на документ {json.dumps(paper, ensure_ascii=False)[:70]}, ссылка {bool(token)}",
            )

            for route, markers in SCREENS:
                path = (
                    route.replace("@event", f"/form/weight/{event}")
                    .replace("@record", f"/pets/{pid}/medical-records/{record}")
                    .replace("@pet", f"/pets/{pid}")
                    .replace("@med", f"/medications/{med}")
                    .replace("@doc", f"/documents/{doc}")
                    .replace("@share", f"/share/medical/{token}")
                )
                needed = {"@record": record, "@med": med, "@doc": doc, "@share": token, "@event": event}
                if any(needed[word] is None for word in needed if word in route):
                    check(f"{route} есть на что смотреть", False, "не создалось то, что открывает этот экран")
                    continue
                if not await open_screen(pg, path):
                    check(f"{route} открывается", False, f"не открылся {path}")
                    continue
                body = await wait_until(pg, lambda text: "Загрузка..." not in text and all(m in text for m in markers))
                check(
                    f"{route} показывает своё",
                    all(m in body for m in markers),
                    f"ждали {markers} по адресу {pg.url}, получили {body[:120]!r}",
                )
                check(f"{route} без текста о сбое", not any(word in body for word in BROKEN), body[:120])
                fits = await fits_screen(pg)
                check(
                    f"{route} без горизонтальной прокрутки",
                    fits is True,
                    "страница ушла из-под вопроса" if fits is None else "",
                )

            await pg.evaluate(
                "async () => { await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }); }"
            )
            for route, markers in [
                ("/login", ["Вход", "Войти"]),
                ("/register", ["Новый аккаунт"]),
                ("/forgot-password", ["Новый пароль", "Отправить ссылку"]),
                ("/privacy", ["Политика конфиденциальности"]),
                ("/consent", ["Согласие на обработку"]),
            ]:
                await open_screen(pg, route)
                body = await wait_until(pg, lambda text: "Загрузка..." not in text and all(m in text for m in markers))
                check(f"без входа {route} показывает своё", all(m in body for m in markers), body[:120])
                check(f"без входа {route} без текста о сбое", not any(word in body for word in BROKEN), body[:120])
        finally:
            if pid:
                # Уборка на устоявшейся странице: иначе вопрос уходит вместе с переездом.
                await open_screen(pg, "/")
                await api(pg, "DELETE", f"/pets/{pid}")
            await b.close()
    return summary("пути по экранам")


asyncio.run(main())
