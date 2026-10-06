"""Правки мелких находок на экранах лекарств и документов: пустое состояние без питомца,
пополнение остатка с подписью под полем, «Напомнить за» про 60 дней, форма без курса,
и удаление документа с одной формулировкой на обоих экранах.

Needs the local stack and the demo data. Works on its own test pet «Тест-М» and removes it."""

import asyncio
import time

from common import BASE, api, async_playwright, check, login, new_page, summary

COURSE = "Т-проверка напомнить"
# Аккаунт без питомцев, только чтобы увидеть экран без питомца: у демо-владельца
# питомцы есть, и пустой список лекарств у него означал бы совсем другое. Имя с
# номером прогона: проверка не падает, если прошлый её аккаунт не удалился (у
# удаления аккаунта свой лимит на час). Удаляется за собой в finally.
NO_PET_PASSWORD = "PetzyCheck2026!"
NO_PET_USERNAME = f"tcheck_nopet{int(time.time()) % 100000}"


async def no_pet_signup(pg) -> int:
    return await pg.evaluate(
        """async ([user, password]) => {
            const res = await fetch('/api/auth/register', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: user, password: password, full_name: 'Без Питомца',
                    email: `${user}@example.invalid`, privacy_consent: true})});
            return res.status;
        }""",
        [NO_PET_USERNAME, NO_PET_PASSWORD],
    )


async def no_pet_cleanup(pg) -> int:
    return await pg.evaluate(
        """async ([password]) => {
            const res = await fetch('/api/me/account', {method: 'DELETE', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({password: password}), credentials: 'include'});
            return res.status;
        }""",
        [NO_PET_PASSWORD],
    )


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        await pg.goto(BASE + "/pets/new")
        await pg.wait_for_timeout(1200)
        await pg.get_by_role("button", name="Собака").click()
        await pg.get_by_placeholder("Имя питомца").fill("Тест-М")
        await pg.get_by_role("button", name="Добавить", exact=True).click()
        await pg.wait_for_timeout(2200)
        await pg.get_by_role("button", name="Готово").click()
        await pg.wait_for_timeout(800)
        pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == "Тест-М")
        try:
            await api(pg, "POST", f"/pets/{pid}/share", {"username": "demo"})
            await pg.evaluate("id => localStorage.setItem('selectedPetId', JSON.stringify(id))", pid)
            await pg.evaluate("name => localStorage.setItem('selectedPetName', JSON.stringify(name))", "Тест-М")
            med = (
                await api(
                    pg,
                    "POST",
                    "/medications",
                    {
                        "pet_id": pid,
                        "name": COURSE,
                        "type": "Таблетка",
                        "default_dose": 1,
                        "dose_unit": "таб",
                        "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["23:58"]},
                        "inventory_enabled": True,
                        "inventory_current": 4,
                        "is_active": True,
                    },
                )
            )["json"]["id"]

            # ---- «Пополнить»: пустое поле говорит под собой, а не тостом после нажатия.
            await pg.goto(BASE + "/medications")
            await pg.wait_for_timeout(2000)
            card = pg.locator(".card-soft", has_text=COURSE).first
            await card.get_by_role("button", name="Пополнить").click()
            await pg.wait_for_timeout(700)
            await pg.locator(".adm-dialog").get_by_text("Добавить", exact=True).click()
            await pg.wait_for_timeout(600)
            check(
                "an empty amount is said under the field, and the dialog stays open",
                await pg.get_by_text("Укажите, сколько купили").count() == 1
                and await pg.get_by_text("Пополнить остаток").count() == 1,
                (await pg.inner_text("body"))[-160:].replace(chr(10), " | "),
            )
            await pg.locator(".adm-dialog").get_by_text("Отмена", exact=True).click()
            await pg.wait_for_timeout(500)

            # ---- «Напомнить за»: потолок в 60 дней назван под полем, а не только в ошибке.
            await pg.goto(BASE + f"/medications/{med}/edit")
            await pg.wait_for_timeout(2000)
            check(
                "the stock reminder field says its 60-day ceiling before it is reached",
                "не больше 60 дней" in await pg.inner_text("body"),
            )
            check(
                "the form's own button says «Сохранить» while editing",
                await pg.get_by_role("button", name="Сохранить", exact=True).count() == 1,
            )
            # The warning is only there once the dose looks like the strength, so it has to be provoked.
            await pg.get_by_label("За один приём").fill("10")
            await pg.wait_for_timeout(500)
            check(
                "the dose hint names the box field, not a direction on the page",
                "впишите их в «На упаковке»" in await pg.inner_text("body"),
                (await pg.inner_text("body"))[:200].replace(chr(10), " | "),
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)

            # ---- Курса нет: не пустая новая форма, а «Такого лекарства нет».
            await pg.goto(BASE + "/medications/000000000000000000000000/edit")
            await pg.wait_for_timeout(2200)
            check(
                "an edit of a course that is gone says so, with a way back to the list",
                await pg.get_by_text("Такого лекарства нет").count() == 1
                and await pg.get_by_role("button", name="К лекарствам").count() == 1
                # and no empty new-course form under it, which is what it used to draw
                and await pg.get_by_text("Название", exact=True).count() == 0,
                (await pg.inner_text("body"))[:160].replace(chr(10), " | "),
            )

            # ---- Новое лекарство: кнопка «Добавить», как в форме документа.
            await pg.goto(BASE + "/medications/new")
            await pg.wait_for_timeout(2000)
            check(
                "a new course is added with «Добавить», as a document is",
                await pg.get_by_role("button", name="Добавить", exact=True).count() == 1
                and await pg.get_by_role("button", name="Создать", exact=True).count() == 0,
                (await pg.inner_text("body"))[:160].replace(chr(10), " | "),
            )

            # ---- Удаление документа: одна формулировка на списке и в форме.
            await pg.evaluate(
                """async ([pid]) => {
                    const fd = new FormData();
                    fd.append('pet_id', pid);
                    fd.append('category', 'vaccination');
                    fd.append('title', 'Т-проверка прививка');
                    fd.append('expires_at', '2027-05-01');
                    fd.append('file', new File([new Uint8Array([37, 80, 68, 70, 45, 49, 46, 52])], 'п.pdf', {type: 'application/pdf'}));
                    await fetch('/api/documents', {method: 'POST', body: fd, credentials: 'include'});
                }""",
                [pid],
            )
            doc = (await api(pg, "GET", f"/documents?pet_id={pid}"))["json"]["documents"][0]
            await pg.goto(BASE + "/documents")
            await pg.wait_for_timeout(2000)
            # Delete sits behind the row's actions menu, as a swipe-only row is unreachable by keyboard otherwise.
            await pg.get_by_role("button", name="Действия: Т-проверка прививка").click()
            await pg.wait_for_timeout(700)
            await pg.locator(".adm-action-sheet-button-item", has_text="Удалить").click()
            await pg.wait_for_timeout(800)
            asked = await pg.inner_text(".adm-dialog")
            check(
                "deleting from the list says the file is erased for good, as the form does",
                "Файл будет стёрт насовсем" in asked,
                asked.replace(chr(10), " | "),
            )
            await pg.locator(".adm-dialog").get_by_text("Отмена", exact=True).click()
            await pg.wait_for_timeout(500)
            await pg.goto(BASE + f"/documents/{doc['_id']}/edit")
            await pg.wait_for_timeout(2000)
            check(
                "the form's own button says «Сохранить» while editing a document",
                await pg.get_by_role("button", name="Сохранить", exact=True).count() == 1,
            )
            # ---- Две записи держат файл, и одна из них напоминает: карточка говорит и то и это.
            for kind, extra in (
                ("vaccination", {"next_due": "2027-05-01"}),
                ("parasite", {"target": "worms"}),
            ):
                made_rec = await api(
                    pg,
                    "POST",
                    "/medical-records",
                    {
                        "pet_id": pid,
                        "kind": kind,
                        "date": "2026-10-01",
                        "title": f"Т-проверка {kind}",
                        "document_ids": [doc["_id"]],
                        **extra,
                    },
                )
                check(f"the record of kind {kind} was made", made_rec["status"] == 201, str(made_rec["status"]))
            await pg.goto(BASE + "/documents")
            await pg.wait_for_timeout(2000)
            card = pg.get_by_text("Т-проверка прививка").first.locator(
                "xpath=ancestor::*[contains(@class,'adm-card')][1]"
            )
            line = await card.inner_text()
            check(
                "a file two records hold says how many in words",
                "и ещё 1 запись" in line and "и ещё 1\n" not in line,
                line.replace(chr(10), " | "),
            )
            check(
                "a file whose record reminds keeps its own date in words",
                "Действует до 01.05.2027" in line and "Напомнит запись из медкарты" in line,
                line.replace(chr(10), " | "),
            )
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")

        # ---- Без питомца: не пустой список, а «Сначала добавьте питомца».
        # Свой аккаунт без питомцев в своём окне: у демо-владельца питомцы есть,
        # и пустой список лекарств у него означал бы совсем другое.
        ctx2, pg2 = await new_page(b, width=390, height=844, sw=False)
        try:
            await pg2.goto(BASE + "/login")
            made = await no_pet_signup(pg2)
            if made == 429:
                # Регистрация на стенде ограничена пятью в час: прогон, который
                # не успел зарегистрироваться, пропускает этот кусок, а не падает.
                print("SKIP the stand refused a new account (registration is 5 per hour)")
            else:
                check("the throwaway account without a pet was made", made == 201, str(made))
                await pg2.goto(BASE + "/medications")
                await pg2.wait_for_timeout(2500)
                body = await pg2.inner_text("body")
                check(
                    "the list without a pet asks for a pet, not for a first medicine",
                    await pg2.get_by_text("Сначала добавьте питомца").count() == 1
                    and "Здесь будут лекарства питомца" not in body,
                    body[:160].replace(chr(10), " | "),
                )
        finally:
            # Удаление аккаунта на стенде ограничено десятью в час, поэтому это
            # заметка, а не проверка: при 429 аккаунт переживёт прогон, и его
            # имя с номером прогона не мешает следующему.
            gone = await no_pet_cleanup(pg2)
            print(f"== the throwaway account {NO_PET_USERNAME} was removed: {gone}")
        await b.close()
    summary("notes on the medicine and document screens")


asyncio.run(main())
