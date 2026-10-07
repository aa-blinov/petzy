"""Вертикальный ритм форм: ряды одной высоты, подпись под заголовком на 4px, кнопка под текстом на 12px.

Три правки, которые на вид почти не видны, но каждый ряд и каждая линия считаются глазом:

1. Высота ряда с одним полем бралась из высоты контрола внутри: 47.5px с переключателем,
   49px с полем ввода, 50.5px со списком. Разделители между полями одной карточки шли
   вразнобой, и к низу формы ритм сжимался. Теперь у ряда одна высота.
2. Подпись под заголовком («Питомец: Рекс», «После смены пароля...») стояла на 2, 8 или
   16px в зависимости от экрана, а таблица отступов требует 4px: это строка того же
   заголовка, а не следующий блок.
3. Подсказка над кнопкой «Добавить поле» складывала два отступа: 8px от текста и 12px от
   кнопки, всего 20px, чего нет на лестнице.

Нужны локальный стенд и демо-данные.
"""

import asyncio
import json

from common import BASE, async_playwright, check, login, new_page, summary, wait_until

# What the spacing table in DESIGN.md gives these gaps.
BYLINE_GAP = 4
TEXT_TO_BUTTON_GAP = 12
# The band a one-field row lives in (--form-row-height is 51px). A row with a note, a textarea,
# a group of choices or a file picker is taller by its own content and is not part of this rhythm,
# so it is left out rather than counted as a second height of the same row.
ONE_FIELD_BAND = (40, 60)
# The block that holds a screen's title: a direct child of the page column, so it is the title's
# own box rather than the 40px header that centres it.
TITLE_BLOCK = ".max-width-container > .safe-area-padding"
# Half a pixel: the row is a whole number of pixels tall, a sub-pixel difference is rounding.
TOLERANCE = 0.5

ROWS = """() => [...document.querySelectorAll('main .adm-list-item')].map((el) => {
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el);
  if (cs.visibility === 'hidden' || cs.display === 'none') return null;
  return { h: Math.round(r.height * 10) / 10, t: (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 24) };
}).filter(Boolean)"""

# The distance from the bottom of one element to the top of the next, when the next sits under it.
GAP_UNDER = """(() => {
  const q = (sel) => document.querySelector('main ' + sel);
  const top = q(%s), bottom = q(%s);
  if (!top || !bottom) return null;
  const r1 = top.getBoundingClientRect(), r2 = bottom.getBoundingClientRect();
  return Math.round((r2.top - r1.bottom) * 10) / 10;
})()"""


async def row_heights(pg) -> list[dict]:
    return await pg.evaluate(ROWS)


async def check_rows_one_height(pg, name: str) -> None:
    """Every one-field row of this form is as tall as the others, so the hairlines keep one rhythm."""
    rows = [r for r in await row_heights(pg) if ONE_FIELD_BAND[0] <= r["h"] <= ONE_FIELD_BAND[1]]
    if len(rows) < 2:
        check(f"{name}: однострочных рядов достаточно, чтобы судить", False, f"рядов {len(rows)}")
        return
    heights = sorted({r["h"] for r in rows})
    spread = heights[-1] - heights[0]
    worst = [f"{r['h']}px «{r['t']}»" for r in rows if r["h"] != heights[0]]
    check(
        f"{name}: однострочные ряды одной высоты",
        spread <= TOLERANCE,
        f"разброс {round(spread, 1)}px, высоты {heights}" + (f", отличаются: {', '.join(worst[:3])}" if worst else ""),
    )


async def check_byline(pg, name: str, top: str, bottom: str) -> None:
    """The line under a screen's title sits 4px under it, in every form that has such a line.

    `top` is where the title's own box ends, which is not always the h1: a header block is 40px
    tall with the title centred in it, so the slack under the text is not a gap between two things
    and must not be counted as one."""
    # The selectors go into the expression itself: Playwright does not pass an argument to a
    # string that is a function expression, and it fails on the call rather than on the page.
    gap = await pg.evaluate(GAP_UNDER % (json.dumps(top), json.dumps(bottom)))
    if gap is None:
        check(f"{name}: строка под заголовком есть", False, f"не нашёл «{bottom}» под «{top}»")
        return
    check(f"{name}: подпись под заголовком {BYLINE_GAP}px", abs(gap - BYLINE_GAP) <= TOLERANCE, f"{gap}px")


async def main() -> None:
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=320, height=568, sw=False)
        pid = await login(pg, "demo", "Рекс")

        # 1. The row height, in three forms whose one-field rows hold a switch, a text input and
        #    a picker at once — the three that used to disagree.
        await pg.goto(BASE + "/form/weight")
        await wait_until(pg, lambda t: "Корм" in t)
        await pg.wait_for_timeout(500)
        await check_rows_one_height(pg, "запись веса")
        check(
            "запись веса: горизонтальной прокрутки нет",
            await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0,
        )
        await check_byline(pg, "запись веса", TITLE_BLOCK, ".safe-area-padding p")

        await pg.goto(BASE + "/medications/new")
        await wait_until(pg, lambda t: "На упаковке" in t)
        await pg.wait_for_timeout(500)
        await check_rows_one_height(pg, "лекарство")
        await check_byline(pg, "лекарство", TITLE_BLOCK, "p.safe-area-padding")

        await pg.goto(BASE + "/documents/new")
        await wait_until(pg, lambda t: "Заметка" in t)
        await pg.wait_for_timeout(500)
        await check_rows_one_height(pg, "документ")

        # 2. The line under a title, in the forms that spell it differently by markup: a <p> next
        #    to the <h1>, and the pet's name inside the header block (a class, not a <p>).
        await pg.goto(BASE + f"/pets/{pid}/medical-records/new")
        await wait_until(pg, lambda t: "Прививка" in t)
        await pg.get_by_text("Прививка", exact=True).first.click()
        await wait_until(pg, lambda t: "Сегодня" in t)
        await pg.wait_for_timeout(500)
        await check_byline(pg, "запись о медкарте", "h1", ".medrec__pet")

        await pg.goto(BASE + "/form-defaults")
        await wait_until(pg, lambda t: "Значения по умолчанию" in t)
        await pg.wait_for_timeout(500)
        await check_byline(pg, "значения по умолчанию", "h1", ".safe-area-padding p")

        await pg.goto(BASE + "/pet-events")
        await wait_until(pg, lambda t: "События питомца" in t)
        await pg.wait_for_timeout(500)
        await check_byline(pg, "события питомца", "h1", ".safe-area-padding p")

        # 3. A button under a line of text is one gap, not two summed.
        await pg.goto(BASE + "/event-types/new")
        await wait_until(pg, lambda t: "Поля" in t)
        await pg.wait_for_timeout(500)
        gap = await pg.evaluate(
            """() => {
              const btn = [...document.querySelectorAll('main button')].find((b) => b.textContent.includes('Добавить поле'));
              // Not `previousElementSibling`: an empty box for the field list stands between the
              // text and the button, and measuring from an empty box reads the button's own margin.
              const note = [...document.querySelectorAll('main p')]
                .find((el) => el.textContent.includes('Дата, время и комментарий'));
              if (!btn || !note) return null;
              return Math.round((btn.getBoundingClientRect().top - note.getBoundingClientRect().bottom) * 10) / 10;
            }"""
        )
        check(
            f"тип события: подсказка к кнопке {TEXT_TO_BUTTON_GAP}px",
            gap is not None and abs(gap - TEXT_TO_BUTTON_GAP) <= TOLERANCE,
            f"{gap}px",
        )

        await b.close()

    summary("ритм форм")


asyncio.run(main())
