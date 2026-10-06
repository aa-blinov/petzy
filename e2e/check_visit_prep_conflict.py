"""«К приёму» written from two devices: the second save is refused with a clear conflict, the other person's note is
shown, and the person chooses what to keep. The form is opened on a scratch pet and it is deleted afterwards."""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

MINE = "Кашляет по ночам"
THEIRS = "Перестал есть совсем"


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
            await api(pg, "PUT", f"/pets/{pid}/visit-prep", {"complaint": MINE, "checks": {"cough": "changed"}})
            await pg.goto(BASE + f"/pets/{pid}/visit-prep")
            await pg.wait_for_timeout(2000)
            field = pg.get_by_label("Что беспокоит")
            check("the saved note is on the screen", await field.input_value() == MINE, await field.input_value())

            # The other device saves while this form is open.
            await api(pg, "PUT", f"/pets/{pid}/visit-prep", {"complaint": THEIRS, "checks": {"appetite": "changed"}})
            await field.fill("Кашель прошёл, но не ест")
            await pg.wait_for_timeout(400)
            await pg.get_by_role("button", name="Сохранить").click()
            await pg.wait_for_timeout(1500)
            t = await pg.inner_text("body")
            check(
                "the save is refused and says the note was changed elsewhere",
                "Заметку изменили в другом месте" in t and "Показать, что там сейчас?" in t,
                t[-200:].replace(chr(10), " | "),
            )
            await pg.screenshot(path="vp_conflict.png")
            await pg.get_by_role("button", name="Показать актуальную").click()
            await pg.wait_for_timeout(1800)
            shown = await pg.get_by_label("Что беспокоит").input_value()
            check(
                "the other person's note is shown, and nothing of it is lost",
                shown == THEIRS,
                shown,
            )
            stored = (await api(pg, "GET", f"/pets/{pid}/medical-card"))["json"]["card"]["visit_prep"]
            check("the refused save changed nothing", stored["complaint"] == THEIRS, str(stored))

            # Saving again from the note that is now on the screen goes through.
            await pg.get_by_label("Что беспокоит").fill(MINE)  # from the version that is now on the screen
            await pg.get_by_role("button", name="Сохранить").click()
            await pg.wait_for_timeout(2500)
            stored = (await api(pg, "GET", f"/pets/{pid}/medical-card"))["json"]["card"]["visit_prep"]
            check("and the next save from the fresh version is kept", stored["complaint"] == MINE, str(stored))
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
        await b.close()
    summary("visit prep conflict")


asyncio.run(main())
