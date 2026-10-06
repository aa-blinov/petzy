"""The undo bar must not let a deletion through without being asked.

Two deletions in a row used to be two bars, and the second one pushed the
first out: the first record went to the server with nobody able to undo it.
And with the last pet, the empty state came up under the bar and answered
«no pets» about a deletion that hadn't been agreed to yet.

Needs the local stack. Works in an account of its own («e2eundo», signed up
once and reused) and removes the pets it makes, so the demo data is never
touched. The account stays behind, empty: signing it up costs one of the
stand's five an hour and deleting it is rate limited too.
"""

import asyncio

from common import BASE, api, async_playwright, check, new_page, summary

USER = "e2eundo"
PASSWORD = "Undo-check-2026"


async def _sign_in_or_sign_up(pg) -> int:
    """A fixed login, so repeated runs reuse the account instead of spending
    one of the stand's five sign-ups an hour."""
    return await pg.evaluate(
        """async ([u, pw, mail]) => {
            const post = (path, body) => fetch('/api' + path, {method: 'POST', credentials: 'include',
                headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
            const in_ = await post('/auth/login', {username: u, password: pw});
            if (in_.ok) return in_.status;
            const reg = await post('/auth/register', {username: u, password: pw, full_name: 'Проверка отмены',
                email: mail, privacy_consent: true});
            return reg.status;
        }""",
        [USER, PASSWORD, f"{USER}@example.com"],
    )


async def _delete_pet(pg, name):
    """The same path a person takes: «Действия» on the card, «Удалить», the question."""
    # The button stays visually hidden until it has focus (a finger uses the
    # swipe), so it is focused and pressed rather than clicked.
    menu = pg.get_by_role("button", name=f"Действия: {name}", exact=True)
    menu.focus()
    await menu.press("Enter")
    await pg.locator(".adm-action-sheet-button-item", has_text="Удалить").last.click()
    # The sheet closes over the question it opened; wait for it to be gone,
    # or its mask keeps swallowing the click on the dialog's button.
    await pg.locator(".adm-action-sheet").wait_for(state="hidden")
    await pg.locator(".adm-dialog-button", has_text="Удалить").last.click()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        try:
            await pg.goto(BASE + "/login")
            # Its own account, so the demo pets and Рекс are never touched.
            status = await _sign_in_or_sign_up(pg)
            check(
                "a throwaway account for this check",
                status in (200, 201),
                str(status),
            )
            ids = []
            for name in ("Тест-М", "Тест-М-2"):
                r = await api(pg, "POST", "/pets", {"name": name, "species": "dog", "gender": "male"})
                ids.append(r["json"]["pet"]["_id"])

            await pg.goto(BASE + "/pets")
            await pg.wait_for_timeout(1500)

            # Two deletions in a row, inside one «Отменить» time.
            await _delete_pet(pg, "Тест-М")
            await pg.wait_for_timeout(600)
            await _delete_pet(pg, "Тест-М-2")
            await pg.wait_for_timeout(400)
            bar = pg.locator(".snackbar")
            check(
                "after the second deletion the bar is still there, with «Отменить»",
                await bar.count() == 1 and await bar.get_by_role("button", name="Отменить").count() == 1,
                await bar.inner_text() if await bar.count() else "no bar",
            )
            check(
                "and it says how many are waiting",
                "Удалено: 2" in await bar.inner_text(),
                await bar.inner_text(),
            )
            await bar.get_by_role("button", name="Отменить").click()
            await pg.wait_for_timeout(800)
            on_server = [q["name"] for q in (await api(pg, "GET", "/pets"))["json"]["pets"]]
            check(
                "«Отменить» brings both back: the server was never asked",
                sorted(on_server) == ["Тест-М", "Тест-М-2"],
                str(on_server),
            )
            check(
                "and both are on the screen again",
                await pg.get_by_text("Тест-М-2", exact=True).count() >= 1,
            )

            # One pet left: deleting it must not answer «no pets» at once.
            await api(pg, "DELETE", f"/pets/{ids[1]}")
            await pg.reload()
            await pg.wait_for_timeout(1500)
            await _delete_pet(pg, "Тест-М")
            await pg.wait_for_timeout(500)
            body = await pg.inner_text("body")
            check(
                "under the bar there is no empty state about the pet that was only just deleted",
                "Здесь будут ваши питомцы" not in body,
                body[:160].replace(chr(10), " | "),
            )
            check(
                "the bar offers to put it back",
                await pg.locator(".snackbar").get_by_role("button", name="Отменить").count() == 1,
            )
            await pg.locator(".snackbar").get_by_role("button", name="Отменить").click()
            await pg.wait_for_timeout(800)
            check(
                "and pressing it does",
                (await api(pg, "GET", "/pets"))["json"]["pets"][0]["name"] == "Тест-М",
            )
        finally:
            for pet_id in ids if "ids" in dir() else []:
                await api(pg, "DELETE", f"/pets/{pet_id}")
            # The account is a fixed login, reused by the next run, so it is
            # only emptied here: deleting it is rate limited per address and
            # would leave the stand in a worse state than an empty account.
            gone = await api(pg, "GET", "/pets")
            if gone["json"]["pets"]:
                print("LEFTOVER pets in the check's account: " + str(gone["json"]["pets"]))
            await b.close()
    summary("undo bar")


asyncio.run(main())
