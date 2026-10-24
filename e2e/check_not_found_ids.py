"""An address with an id that is not there says «не найдено» with the right noun, and keeps «Сервер не ответил» for failures.

P-02: /event-types/zzz/edit is «Тип записи не найден», not «Загружаем…» for ever. P-04, P-05: a malformed id (the API
answers 422) and an unknown record under a real pet are «не найдено» too, with no useless «Повторить»; a record that is
gone is not blamed on the pet.

Read only: the demo pet «Рекс» is opened, nothing is written.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary, wait_until

UNKNOWN_ID = "0123456789abcdef01234567"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        _ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        pet_id = await pg.evaluate("JSON.parse(localStorage.getItem('selectedPetId'))")

        async def says(path, word, name, absent=("Повторить", "Сервер не ответил", "Загружаем")):
            await pg.goto(BASE + path)
            text = await wait_until(pg, lambda t: word in t, timeout=12_000)
            check(f"{name}: «{word}»", word in text, text[:160].replace("\n", " | "))
            for gone in absent:
                check(f"{name}: no «{gone}»", gone not in text)

        await says("/event-types/zzz/edit", "Тип записи не найден", "an unknown event type")
        await says("/pets/nope/medical-card", "Питомец не найден", "a malformed pet id on the card")
        await says("/pets/nope/edit", "Питомец не найден", "a malformed pet id on its form")
        await says("/medications/zzz/edit", "Такого лекарства нет", "a malformed medication id")
        await says("/documents/zzz/edit", "Такого документа нет", "a malformed document id")
        await says(
            f"/pets/{pet_id}/medical-records/zzz",
            "Запись не найдена",
            "a malformed record id",
            absent=("Питомец не найден", "Повторить", "Сервер не ответил"),
        )
        await says(
            f"/pets/{pet_id}/medical-records/{UNKNOWN_ID}",
            "Запись не найдена",
            "an unknown record under a real pet",
            absent=("Питомец не найден", "Повторить", "Сервер не ответил"),
        )
        await b.close()
    return summary("«не найдено» с нужным словом")


asyncio.run(main())
