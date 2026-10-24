"""A date typed in digits is never dropped in silence, and the repeat date follows the record's date.

P-01: «31.02.2026», «12.1» typed into a date show a message and «Сохранить» is refused: the record keeps its date only
because nothing was saved, not because the form forgot what was typed. P-20: the limit message says what is wrong.
P-22: «Следующая» put in by an interval button follows the record's date, also when the record is edited, and the button
stays pressed; a date set by hand does not move.

Needs the local stack and the demo data. Makes a scratch pet of its own and removes it.
"""

import asyncio
from datetime import date, datetime

from common import BASE, api, async_playwright, check, login, new_page, settle, summary, wait_until
from scratch import add_months, digits, drop_pet, make_pet, make_record, ru

DATE_LABEL = "Когда сделана прививка"


async def pressed(pg, name):
    return await pg.get_by_role("button", name=name, exact=True).get_attribute("aria-pressed")


async def next_text(pg):
    """What the «Следующая» block says: its value, its choices."""
    return await pg.locator(".datefield-group").nth(1).inner_text()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        _ctx, pg = await new_page(b, width=390, height=844, sw=False)
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await login(pg, "demo", "Рекс")
        pid = await make_pet(pg)
        try:
            today = datetime.now().astimezone().date()
            first = add_months(today.replace(day=15), -1)
            typed = add_months(today.replace(day=10), -1)
            rid = await make_record(
                pg, pid, "vaccination", "Нобивак", first.isoformat(), next_due=add_months(first, 12).isoformat()
            )
            url = f"{BASE}/pets/{pid}/medical-records/{rid}"

            async def record():
                rows = (await api(pg, "GET", f"/medical-records?pet_id={pid}"))["json"]["records"]
                return next(r for r in rows if r["kind"] == "vaccination")

            await pg.goto(url)
            await settle(pg)
            await pg.get_by_role("button", name="Ввести цифрами", exact=True).nth(0).click()
            typed_date = pg.locator(f'input[aria-label="{DATE_LABEL}, цифрами"]')

            # P-01: an impossible date
            await typed_date.fill("31022026")
            body = await wait_until(pg, lambda t: "Такой даты нет" in t)
            check("an impossible date is named", "Такой даты нет" in body)
            await pg.get_by_role("button", name="Сохранить", exact=True).click()
            await settle(pg, 300)
            check(
                "and the save is refused, the form stays",
                rid in pg.url and "Запись сохранена" not in await pg.inner_text("body"),
            )
            saved = await record()
            check("the record keeps its date and its repeat", saved["date"] == first.isoformat(), str(saved["date"]))

            # P-01: an unfinished date
            await typed_date.fill("121")
            await pg.get_by_role("button", name="Сохранить", exact=True).click()
            body = await wait_until(pg, lambda t: "Введите дату полностью" in t)
            check("an unfinished date is refused with its message", "Введите дату полностью" in body and rid in pg.url)
            check("and nothing was saved", (await record())["date"] == first.isoformat())

            # P-20: what is wrong with a date out of range
            await typed_date.fill("01012099")
            body = await wait_until(pg, lambda t: "не может быть в будущем" in t)
            check(
                "a future date of a record says it is in the future", "Дата не может быть в будущем" in body, body[:300]
            )
            await typed_date.fill("")
            await pg.get_by_role("button", name="Ввести цифрами", exact=True).nth(1).click()
            typed_next = pg.locator('input[aria-label="Следующая, цифрами"]')
            await typed_next.fill("01012020")
            body = await wait_until(pg, lambda t: "Дата уже прошла" in t)
            check("a past repeat date says it has passed", "Дата уже прошла" in body, body[:300])

            # a right date goes in, and the repeat follows it (P-22 in the edit form)
            await pg.get_by_role("button", name="Ввести цифрами", exact=True).nth(1).click()
            await typed_date.fill(digits(typed))
            await settle(pg, 200)
            text = await next_text(pg)
            check(
                "the repeat of an edited record follows the date, by the same interval",
                ru(add_months(typed, 12)) in text,
                text,
            )
            check("and its button stays pressed", await pressed(pg, "Через год") == "true")
            await pg.get_by_role("button", name="Сохранить", exact=True).click()
            await settle(pg, 300)
            saved = await record()
            check(
                "saved: the new date and the moved repeat",
                saved["date"] == typed.isoformat() and saved["next_due"] == add_months(typed, 12).isoformat(),
                f"{saved['date']} {saved['next_due']}",
            )

            # P-22: the buttons stay pressed through changes of the date
            await pg.goto(url)
            await settle(pg)
            await pg.get_by_role("button", name="Через 3 месяца", exact=True).click()
            await pg.get_by_role("button", name="Вчера", exact=True).click()
            await settle(pg, 200)
            yesterday = date.fromordinal(today.toordinal() - 1)
            text = await next_text(pg)
            check("«Через 3 месяца» follows «Вчера»", ru(add_months(yesterday, 3)) in text, text)
            check("and stays pressed", await pressed(pg, "Через 3 месяца") == "true")
            await pg.get_by_role("button", name="Сегодня", exact=True).click()
            await settle(pg, 200)
            text = await next_text(pg)
            check("and follows «Сегодня» too", ru(add_months(today, 3)) in text, text)
            check("still pressed", await pressed(pg, "Через 3 месяца") == "true")

            # a date set by hand is the person's own
            await pg.get_by_role("button", name="Ввести цифрами", exact=True).nth(1).click()
            await pg.locator('input[aria-label="Следующая, цифрами"]').fill("01012030")
            await settle(pg, 200)
            await pg.get_by_role("button", name="Вчера", exact=True).click()
            await settle(pg, 200)
            text = await next_text(pg)
            check("a repeat date typed by hand does not move", "01.01.2030" in text, text)
        finally:
            await drop_pet(pg, pid)
            await b.close()
    return summary("дата цифрами и повтор за датой")


asyncio.run(main())
