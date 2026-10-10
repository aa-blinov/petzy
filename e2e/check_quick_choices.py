"""Quick choices that answer a field in one tap, and say they were pressed.

The «Когда было» row («Сейчас», «Час назад», «2 часа назад») and the «Как раньше» row (the last
portions or weights) write the answer into the form and never said so: every chip was drawn with
`pressed={false}`, so nothing was ever marked and a thumb got no answer to its own tap. Worse than
silence, the person has to read the date field to learn what the tap did.

The chip is marked while the fields still hold what that chip wrote, and gives the mark up the moment
the answer is changed by hand. Marking by recomputing «two hours ago» from the clock would be wrong
the other way: the target moves on with the clock, and a minute into filling the form every chip
would unmark itself under the finger that had just pressed it.

Needs the local stack and the demo data. Writes one weighing on the demo pet and removes it after.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, swipe_wheel, wait_until

WHEN_CHIPS = ["Сейчас", "Час назад", "2 часа назад", "Вчера в это время"]


async def pressed(pg, group: str) -> list[str]:
    """Which chips of a group say they are pressed, the way a screen reader hears them."""
    return await pg.evaluate(
        '(g) => [...document.querySelectorAll(`[role=group][aria-label="${g}"] .choice-chip`)]'
        ".filter((c) => c.getAttribute('aria-pressed') === 'true')"
        ".map((c) => c.textContent.trim())",
        group,
    )


def minutes(text):
    h, _, m = text.strip().partition(":")
    return int(h) * 60 + int(m) if h.isdigit() and m.isdigit() else None


async def open_weight_form(pg):
    await pg.goto(BASE + "/")
    await wait_until(pg, lambda t: "Рекс" in t)
    await pg.locator(".app-fab").click()
    # The sheet of event types, waited for as a sheet: the name of the type is also on the form the
    # sheet opens, so waiting for the text alone passes before the sheet has even arrived. Waiting on
    # `.adm-popup` itself does not work either — the wrapper has no box of its own, so it reads as
    # hidden while the sheet stands there fully drawn; the button inside it does have a box.
    sheet = pg.locator(".adm-popup").filter(has_text="Что записать?")
    weight_in_sheet = sheet.get_by_text("Вес", exact=True).first
    await weight_in_sheet.wait_for(state="visible", timeout=8000)
    await weight_in_sheet.click()
    await wait_until(pg, lambda t: "/form/weight" in pg.url and "Когда было" in t)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)

        # «Как раньше» only draws for a pet that has records of this kind, so one is written first.
        pid = await login(pg, "demo", "Рекс")

        async def weights():
            body = (await api(pg, "GET", f"/events?pet_id={pid}&type=weight"))["json"] or {}
            return [r["_id"] for r in body.get("items") or body.get("events") or []]

        before = await weights()
        await api(
            pg,
            "POST",
            "/events",
            {"pet_id": pid, "type": "weight", "date": "2026-01-15", "time": "10:00", "fields": {"weight": 12.4}},
        )
        made = [i for i in await weights() if i not in before]

        try:
            await open_weight_form(pg)

            # The «запоминать» switch, tapped on the form as it opens. The weight field holds the focus
            # then, and it is empty: leaving it says what is still missing, that line appears under the
            # field, and everything below moves down before the finger is up. Without a guard on the press
            # the tap lands on the row that used to be there and the switch never moves.
            sw = pg.locator('[role="switch"][aria-label="Запоминать значения"]')
            await sw.scroll_into_view_if_needed()
            await pg.wait_for_timeout(400)

            # The switch sits in a block of its own, so both its name and what it does have the
            # full width and stay on one line each. In a row of the horizontal form the label
            # column is 7em (107px at 320px) and any name of two words breaks onto a second line.
            block_lines = await pg.evaluate(
                """() => {
                  const sw = document.querySelector('[role="switch"][aria-label="Запоминать значения"]');
                  const block = sw && sw.closest('.choice-block');
                  if (!block) return null;
                  const lines = (el) => {
                    const r = document.createRange();
                    r.selectNodeContents(el);
                    const rects = [...r.getClientRects()].filter((x) => x.width > 1 && x.height > 1);
                    return new Set(rects.map((x) => Math.round(x.top))).size;
                  };
                  const label = block.querySelector('.remember-row__label');
                  const note = block.querySelector('.choice-block__hint');
                  return {
                    label: label ? label.textContent.trim() : null,
                    labelLines: label ? lines(label) : 0,
                    note: note ? note.textContent.trim() : null,
                    noteLines: note ? lines(note) : 0,
                    switchH: Math.round(sw.getBoundingClientRect().height),
                    rowH: Math.round(block.querySelector('.remember-row').getBoundingClientRect().height),
                  };
                }"""
            )
            check(
                "the switch names itself and says what it does, both in one line",
                block_lines is not None
                and block_lines["label"] == "Запоминать значения"
                and block_lines["note"] == "Подставлять в следующие записи этого вида"
                and block_lines["labelLines"] == 1
                and block_lines["noteLines"] == 1,
                block_lines,
            )
            check(
                "and its row is a thumb tall in both positions",
                block_lines is not None and block_lines["rowH"] >= 44 and block_lines["switchH"] > 0,
                f"ряд {block_lines['rowH'] if block_lines else '?'}px, переключатель {block_lines['switchH'] if block_lines else '?'}px",
            )

            await sw.click()
            await pg.wait_for_timeout(400)
            check(
                "the «запоминать» switch takes the tap on the form as it opens, focus and all",
                await sw.get_attribute("aria-checked") == "true",
                await sw.get_attribute("aria-checked"),
            )
            size_on = await sw.bounding_box()
            await sw.click()
            await pg.wait_for_timeout(400)
            size_off = await sw.bounding_box()
            check(
                "and takes it back, at the same size both ways",
                await sw.get_attribute("aria-checked") == "false"
                and abs(size_on["width"] - size_off["width"]) < 1
                and abs(size_on["height"] - size_off["height"]) < 1,
                f"включён {round(size_on['width'])}x{round(size_on['height'])}, выключен {round(size_off['width'])}x{round(size_off['height'])}",
            )

            # The weight is in now, so nothing appears or disappears under the finger for the rest:
            # an empty field with the focus says what is still missing when it is left, and that line
            # moves everything below it.
            await pg.fill("#weight", "12,4")
            await pg.wait_for_timeout(300)

            body = await pg.inner_text("body")
            check(
                "the quick row of times is on a new record",
                all(c in body for c in WHEN_CHIPS),
                [c for c in WHEN_CHIPS if c not in body],
            )
            check(
                "nothing is pressed before a tap: a chip says what was chosen, not what is there by default",
                await pressed(pg, "Когда") == [],
                await pressed(pg, "Когда"),
            )

            await pg.get_by_role("button", name="2 часа назад", exact=True).click()
            await pg.wait_for_timeout(400)
            check(
                "the pressed chip is marked", await pressed(pg, "Когда") == ["2 часа назад"], await pressed(pg, "Когда")
            )
            check(
                "and only it: the neighbour «Час назад» is not marked as well",
                await pg.get_by_role("button", name="Час назад", exact=True).get_attribute("aria-pressed") == "false",
            )

            # The answer it wrote, read off the form rather than off the chip: a chip that marks itself
            # and writes the wrong time is not an answer.
            shown = (await pg.locator("#time").inner_text()).strip()
            now = await pg.evaluate("() => { const d = new Date(); return d.getHours() * 60 + d.getMinutes(); }")
            # The clock is round the day: 22:03 and 00:03 are two hours apart, not twenty-two.
            gap = ((minutes(shown) - (now - 120)) % 1440) if minutes(shown) is not None else 999
            off = min(gap, 1440 - gap)
            check(
                "and the time in the form is the one it claims to be",
                off <= 1,
                f"в форме {shown}, сейчас {now // 60}:{now % 60:02d}",
            )

            await pg.wait_for_timeout(400)
            check(
                "still marked right after: recomputing «two hours ago» would have unmarked it already",
                await pressed(pg, "Когда") == ["2 часа назад"],
                await pressed(pg, "Когда"),
            )

            # Changed by hand through the time wheel: the chip gives the mark up, because it no longer
            # says what is in the form.
            await pg.locator("#time").click()
            await pg.wait_for_timeout(700)
            await swipe_wheel(pg, ctx, 0, 1, up=False)
            await pg.locator(".adm-picker-header-button", has_text="Готово").last.click()
            await pg.locator(".adm-picker-view-column-wheel").first.wait_for(state="hidden", timeout=8000)
            await pg.wait_for_timeout(400)
            moved = (await pg.locator("#time").inner_text()).strip()
            check("the time is changed by hand", moved != shown, f"было {shown}, стало {moved}")
            check(
                "and the mark is given up with it",
                await pressed(pg, "Когда") == [],
                await pressed(pg, "Когда"),
            )

            await pg.get_by_role("button", name="Сейчас", exact=True).click()
            await pg.wait_for_timeout(400)
            check(
                "another chip takes the mark over", await pressed(pg, "Когда") == ["Сейчас"], await pressed(pg, "Когда")
            )

            # «Как раньше»: the last values of this pet, one tap instead of typing them again.
            body = await pg.inner_text("body")
            if "Как раньше" not in body:
                check(
                    "the «Как раньше» row is on a form whose pet has records of this kind",
                    False,
                    "нет строки «Как раньше»",
                )
            else:
                chip = await pg.evaluate(
                    "() => document.querySelector('[role=group][aria-label=\"Как раньше\"] .choice-chip')?.textContent.trim()"
                )
                await pg.get_by_role("button", name=chip, exact=True).click()
                await pg.wait_for_timeout(400)
                check(
                    "a «as before» value is marked once it fills the field",
                    await pressed(pg, "Как раньше") == [chip],
                    await pressed(pg, "Как раньше"),
                )
                in_field = await pg.input_value("#weight")
                check(
                    "and the field really holds that value",
                    in_field.replace(",", ".") == chip.replace(",", "."),
                    f"в поле {in_field}, на кнопке {chip}",
                )
                await pg.fill("#weight", "9,9")
                await pg.wait_for_timeout(400)
                check(
                    "and gives the mark up when the value is changed by hand",
                    await pressed(pg, "Как раньше") == [],
                    await pressed(pg, "Как раньше"),
                )
            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            for i in made:
                await api(pg, "DELETE", f"/events/{i}")
        await b.close()
    summary("quick choices")


asyncio.run(main())
