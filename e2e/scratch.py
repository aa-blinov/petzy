"""A scratch pet «Тест-М» for the checks that need records of their own, and the dates they write them on."""

from datetime import date, timedelta

from common import BASE, api, settle

NAME = "Тест-М"


async def make_pet(pg, profile=None):
    """A new dog «Тест-М», and its id. `profile` (clinics with doctors) is put into its medical profile."""
    await pg.goto(BASE + "/pets/new")
    await settle(pg)
    await pg.get_by_role("button", name="Собака").click()
    await pg.get_by_placeholder("Имя питомца").fill(NAME)
    await pg.get_by_role("button", name="Добавить", exact=True).click()
    await settle(pg, 150)
    if await pg.get_by_role("button", name="Готово").count():
        await pg.get_by_role("button", name="Готово").click()
    await settle(pg, 150)
    pid = next(q["_id"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"] if q["name"] == NAME)
    if profile:
        await api(pg, "PUT", f"/pets/{pid}/medical-profile", profile)
    return pid


async def drop_pet(pg, pid):
    await pg.goto(BASE + "/")
    await settle(pg)
    await api(pg, "DELETE", f"/pets/{pid}")


async def make_record(pg, pid, kind, title, day, **more):
    """A medical record by the API, and its id."""
    answer = await api(
        pg, "POST", "/medical-records", {"pet_id": pid, "kind": kind, "title": title, "date": day, **more}
    )
    assert answer["status"] in (200, 201), answer
    return answer["json"]["id"]


def add_months(day: date, months: int) -> date:
    """The same day `months` on; the day stays in the month it lands in (the form's own rule)."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


def ru(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def digits(day: date) -> str:
    return day.strftime("%d%m%Y")
