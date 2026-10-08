"""A record whose answer got lost, and a record that would not load.

Two failures of the same form, neither of which may cost the person a record or throw them out of
the screen they are on:

- the create reaches the server and its answer is lost: pressing «Создать» again must not leave two
  records about one weighing, and the retry leaves the form as a saved one does;
- the record to edit does not load: the form says so on itself, offers another try and a way back,
  instead of jumping to the feed, where «Назад» would open the same form again.

Needs the local stack and the demo data. Records only a scratch pet of its own, and removes it.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary


async def records(pg, pet_id: str, type_key: str) -> list[dict]:
    body = (await api(pg, "GET", f"/events?pet_id={pet_id}&type={type_key}"))["json"]
    return body.get("items") or body.get("events") or []


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
            # The request goes through and is written, the browser is told the connection broke:
            # exactly the moment a person answers «Сервер не ответил» by pressing again.
            lost = {"on": True}

            async def lose_the_answer(route):
                if lost["on"] and route.request.method == "POST" and route.request.url.endswith("/api/events"):
                    await route.fetch()
                    await route.abort("failed")
                else:
                    await route.continue_()

            await pg.route("**/api/events", lose_the_answer)
            # Opened the way a person opens it, from the feed's round «+». Opening the form by address instead makes
            # the leave-at-once a step back in the browser's own history (another document), which reloads the page
            # and drops everything the app had on screen, the bar included.
            await pg.goto(BASE + "/")
            await pg.wait_for_timeout(2000)
            await pg.locator(".app-fab").click()
            await pg.wait_for_timeout(1000)
            await pg.get_by_text("Вес", exact=True).first.click()
            await pg.wait_for_timeout(1800)
            check("the form of a weighing opened from the feed", "/form/weight" in pg.url, pg.url.replace(BASE, ""))
            await pg.get_by_label("Вес (кг)").fill("12,4")
            await pg.get_by_role("button", name="Создать").click()
            await pg.wait_for_timeout(2500)
            body = await pg.inner_text("body")
            check(
                "the form stays open and says the server did not answer",
                "/form/weight" in pg.url and ("Сервер не ответил" in body or "Нет связи" in body),
                (pg.url.replace(BASE, "") + " | " + body[:120].replace(chr(10), " | ")),
            )
            # Nothing tells the person to wait: the server may answer at once, and pressing again
            # is safe, the server answers that the record is already written.
            check(
                "the refusal promises no wait it cannot keep",
                "через минуту" not in body,
                [line for line in body.split(chr(10)) if "Сервер не ответил" in line][:2],
            )
            check(
                "the record is written on the server, the person was only not told",
                len(await records(pg, pid, "weight")) == 1,
                str(await records(pg, pid, "weight")),
            )

            lost["on"] = False
            await pg.get_by_role("button", name="Создать").click()
            await pg.wait_for_timeout(3000)
            body = await pg.inner_text("body")
            check(
                "the repeat is answered as a saved record, not a refusal, and the form lets go",
                "/form/weight" not in pg.url and "Запись уже сохранена" in body,
                (pg.url.replace(BASE, "") + " | " + body[:120].replace(chr(10), " | ")),
            )
            rows = await records(pg, pid, "weight")
            check(
                "one weighing, not two",
                len(rows) == 1 and float(rows[0]["fields"]["weight"]) == 12.4,
                str([r["fields"] for r in rows]),
            )

            # The record to edit does not load.
            record_id = rows[0]["_id"]

            async def lose_the_record(route):
                if route.request.method == "GET" and route.request.url.endswith(f"/api/events/{record_id}"):
                    await route.abort("failed")
                else:
                    await route.continue_()

            await pg.unroute("**/api/events", lose_the_answer)
            await pg.route("**/api/events/*", lose_the_record)
            await pg.goto(BASE + f"/form/weight/{record_id}")
            await pg.wait_for_timeout(2500)
            body = await pg.inner_text("body")
            check(
                "the form says on itself that the record did not load",
                "Запись не загрузилась" in body,
                (pg.url.replace(BASE, "") + " | " + body[:160].replace(chr(10), " | ")),
            )
            # Two ways back on purpose: the navbar's and the one inside the notice, so a thumb that landed on the notice is
            # not a dead end.
            check(
                "with another try and a way back, and not thrown out to the feed",
                pg.url.endswith(f"/form/weight/{record_id}")
                and await pg.get_by_role("button", name="Повторить").count() == 1
                and await pg.get_by_role("button", name="Назад").count() >= 1,
                pg.url.replace(BASE, ""),
            )

            await pg.unroute("**/api/events/*", lose_the_record)
            await pg.get_by_role("button", name="Повторить").click()
            await pg.wait_for_timeout(2500)
            check(
                "«Повторить» loads the record",
                await pg.get_by_label("Вес (кг)").count() == 1
                and "Запись не загрузилась" not in await pg.inner_text("body"),
                (await pg.inner_text("body"))[:160].replace(chr(10), " | "),
            )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("record save")


asyncio.run(main())
