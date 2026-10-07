"""Линии-разделители: одна длина на весь экран, и только там, где есть что отделять.

Правило, которое владелец назвал после разбора экранов: блоки разделяет линия, а не отступ.
До правки в antd-формах линия шла по содержимому ряда (`--border-inner`), то есть начиналась
от подписи, а не от края карточки, и на экране оказывались две длины одной линии. В форме
типа события, чьи поля не antd `Form`, разделителей не было вовсе: блоки держались на
отступах, а единственная линия была подчёркиванием поля.

Что проверяет этот файл:

1. Все линии-разделители на форме одной длины. Считаются только те, чьим стилем владеет
   приложение: верхняя граница ряда, секции и блока кнопок, псевдоэлемент блока вне
   antd-формы. Рамки кнопок, чипов и карточек сюда не попадают: это края элементов,
   а не разделители.
2. Нет лишней линии: первому блоку группы и ряду под заголовком секции, над которым уже
   есть линия карточки, она не нужна.
3. Под текстом блока линия оставляет 12px (с самой линией 13), как у поля в antd-форме.
4. Горизонтальной прокрутки нет ни на одной из форм.

Нужны локальный стенд и демо-данные.
"""

import asyncio

from common import BASE, async_playwright, check, login, new_page, summary, wait_until

# 12px от линии до текста блока. У antd-ряда сверху 12px, у блока вне формы -- то же.
LINE_TO_TEXT = 12
# Замер идёт до первой строки текста, а у заголовка секции с плотным межстрочным интервалом
# строка поднимается на 1px выше рамки содержимого. Поэтому 11px -- это те же 12px на глаз,
# а вот меньше -- уже линия налезает на текст.
LINE_TO_TEXT_MIN = LINE_TO_TEXT - 1
# Полпикселя: блок целый, разница в меньшем -- округление.
TOLERANCE = 0.5

# Линии, которыми рисует приложение: верхняя граница ряда, секции и блока кнопок в antd-форме,
# псевдоэлемент блока, который не в antd-форме. Считается и граница содержимого ряда: именно
# там линия жила до правки, и из-за неё на экране оказывались две длины одной линии. Рамки
# кнопок, чипов и карточек сюда не попадают: это края элементов, а не разделители.
LINES = """() => {
  const main = document.querySelector('main');
  if (!main) return null;
  const shown = (el) => {
    const cs = getComputedStyle(el);
    return cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  const textTop = (el) => {
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) {
      if (!n.textContent.trim()) continue;
      const r = document.createRange();
      r.selectNodeContents(n);
      const box = r.getBoundingClientRect();
      if (box.height > 0) return box.top;
    }
    const kid = el.querySelector('*');
    return kid && shown(kid) ? kid.getBoundingClientRect().top : null;
  };
  const lines = [];
  const push = (w, left, top, blockTop, what) => {
    const t = textTop(blockTop.el);
    lines.push({ w: Math.round(w * 10) / 10, left: Math.round(left), top: Math.round(top),
                 gap: t === null ? null : Math.round((t - top) * 10) / 10, what });
  };
  for (const el of main.querySelectorAll('.adm-list-item, .adm-list-card, .choice-block, .adm-list-item-content')) {
    if (!shown(el)) continue;
    const cs = getComputedStyle(el);
    if (parseFloat(cs.borderTopWidth) < 0.5 || cs.borderTopStyle !== 'solid') continue;
    const r = el.getBoundingClientRect();
    push(r.width, r.left, r.top, { el }, (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 18));
  }
  for (const el of main.querySelectorAll('.form-section')) {
    if (!shown(el)) continue;
    const be = getComputedStyle(el, '::before');
    if (be.content === 'none' || parseFloat(be.borderTopWidth) < 0.5) continue;
    const r = el.getBoundingClientRect();
    const left = parseFloat(be.left) || 0, right = parseFloat(be.right) || 0;
    push(r.width - left - right, r.left + left, r.top, { el }, (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 18));
  }
  // Первое, с чего начинается форма, и ряд под заголовком секции: над ними отделять нечего.
  const bare = [];
  for (const sel of ['.adm-form .adm-list-body-inner > :first-child',
                     '.adm-form .adm-list-body-inner > :first-child > *',
                     '.adm-form .adm-list-header + *',
                     '.adm-form .adm-list-header + * > *']) {
    for (const el of main.querySelectorAll(sel)) {
      if (!shown(el)) continue;
      if (parseFloat(getComputedStyle(el).borderTopWidth) >= 0.5) bare.push(sel);
    }
  }
  return { lines, bare, overflow: document.documentElement.scrollWidth - innerWidth };
}"""

FORMS = [
    ("запись веса", "/form/weight", "Корм"),
    ("лекарство", "/medications/new", "На упаковке"),
    ("питомец, новый", "/pets/new", "Имя питомца"),
    ("документ, новый", "/documents/new", "Название"),
    ("тип события, новый", "/event-types/new", "Поля"),
    ("медкарта питомца", "@profile", "Чем кормят"),
    ("запись о медкарте", "@medrec", "Сегодня"),
    ("подготовка к визиту", "@visit", "К чему"),
    ("настройки, пароль", "/settings/password", "Текущий пароль"),
]


async def open_form(pg, path, ready):
    if path == "@profile":
        pet = await pg.evaluate("JSON.parse(localStorage.getItem('selectedPetId'))")
        await pg.goto(BASE + f"/pets/{pet}/medical-profile")
    elif path == "@medrec":
        pet = await pg.evaluate("JSON.parse(localStorage.getItem('selectedPetId'))")
        await pg.goto(BASE + f"/pets/{pet}/medical-records/new")
        await wait_until(pg, lambda t: "Прививка" in t)
        await pg.get_by_text("Прививка", exact=True).first.click()
    elif path == "@visit":
        pet = await pg.evaluate("JSON.parse(localStorage.getItem('selectedPetId'))")
        await pg.goto(BASE + f"/pets/{pet}/visit-prep")
    else:
        await pg.goto(BASE + path)
    await wait_until(pg, lambda t: ready in t, timeout=15_000)
    await pg.wait_for_timeout(600)


async def check_lines(pg, name: str, with_gap: bool = True) -> None:
    """Every divider on this form is as long as every other one, and the form does not scroll sideways."""
    got = await pg.evaluate(LINES)
    if got is None or not got["lines"]:
        check(f"{name}: есть линии-разделители", False, "ни одной не нашёл")
        return
    widths = sorted({line["w"] for line in got["lines"]})
    check(
        f"{name}: линии одной длины ({widths[0]:.0f}px)",
        len(widths) == 1,
        f"{len(got['lines'])} линий, длины {widths}" if len(widths) > 1 else f"{len(got['lines'])} линий",
    )
    check(f"{name}: горизонтальной прокрутки нет", got["overflow"] == 0, f"{got['overflow']}px")
    if not with_gap:
        return
    check(
        f"{name}: под линией первого блока пустоты нет",
        not got["bare"],
        "линия на " + ", ".join(sorted(set(got["bare"]))) if got["bare"] else "",
    )
    gaps = [line["gap"] for line in got["lines"] if line["gap"] is not None]
    tight = [g for g in gaps if g < LINE_TO_TEXT_MIN - TOLERANCE]
    check(
        f"{name}: под линией {LINE_TO_TEXT}px",
        not tight,
        f"{tight}px из {sorted(gaps)}" if tight else f"{min(gaps)}..{max(gaps)}px",
    )


async def main() -> None:
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")

        # 320px: самое узкое, где линия должна уместиться и не поехать по горизонтали.
        ctx, pg = await new_page(b, width=320, height=568, sw=False)
        await login(pg, "demo", "Рекс")
        for name, path, ready in FORMS:
            await open_form(pg, path, ready)
            await check_lines(pg, name)
        await ctx.close()

        # 390px: та же длина в расчёте на другую ширину экрана, на трёх формах с разной
        # структурой: ряды в antd-карточке, блок кнопок выбора и блоки вне antd-формы.
        ctx, pg = await new_page(b, width=390, height=568, sw=False)
        await login(pg, "demo", "Рекс")
        for name, path, ready in [FORMS[1], FORMS[4], FORMS[0]]:
            await open_form(pg, path, ready)
            await check_lines(pg, f"{name}, 390px", with_gap=False)
        await ctx.close()

        await b.close()

    summary("линии-разделители")


asyncio.run(main())
