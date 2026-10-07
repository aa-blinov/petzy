"""Every row of choice buttons marks the one that was pressed, and says so honestly.

The record form's quick row was drawn with `pressed={false}` on every chip: the tap filled the field
and nothing showed for it. That was one row on one screen, but a row of choice buttons is a shared
component, so this check walks the screens that have them and asks the same question everywhere: press
a chip that is not marked, and that chip becomes marked.

Two kinds of rows answer differently, and both answers are right:

- a row of one answer at a time (was the visit as before, a quick date, a repeat) has exactly one
  marked chip, and it is the one pressed;
- a row of words to put into a field (what the pet eats) marks every chip whose words are already in
  that field. Pressing one adds its words and marks it, and the chips marked before stay marked,
  because their words are still in the field. Only a chip with nothing left to say is unpressed.

Needs the local stack and the demo data. The documents are written to reach the filter row, which is
drawn from eleven files and up, and every one of them is removed afterwards.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary, wait_until

# A one-pixel PNG, the smallest thing the document check will accept as a file.
TINY_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

MAKE_DOCS = """async ([id, n]) => {
  const bin = atob('%s');
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const made = [];
  for (let i = 0; i < n; i++) {
    const fd = new FormData();
    fd.append('pet_id', id);
    fd.append('category', 'other');
    fd.append('title', 'Отметка для фильтра ' + i);
    fd.append('file', new File([bytes], 'mark.png', { type: 'image/png' }));
    const r = await fetch('/api/documents', { method: 'POST', body: fd, credentials: 'include' });
    if (r.ok) { const j = await r.json(); made.push(j.id ?? (j.document ?? {})._id); }
  }
  return made;
}"""


async def marked(group) -> list[str]:
    return await group.evaluate(
        "g => [...g.querySelectorAll('.choice-chip')].filter((c) => c.getAttribute('aria-pressed') === 'true').map((c) => c.textContent.trim())"
    )


async def check_row(pg, group, name: str, exclusive: bool = True) -> None:
    """Press an unmarked chip and require the right answer for the kind of row this is."""
    chips = group.locator(".choice-chip")
    total = await chips.count()
    if total < 2:
        check(f"{name}: в строке есть что нажимать", False, f"кнопок {total}")
        return

    before = await marked(group)
    target = None
    for i in range(total):
        if (await chips.nth(i).inner_text()).strip() not in before:
            target = i
            break
    if target is None:
        check(f"{name}: есть кнопка, которую можно нажать", False, f"отмечены все: {before}")
        return

    label = (await chips.nth(target).inner_text()).strip()
    await chips.nth(target).click()
    await pg.wait_for_timeout(350)
    after = await marked(group)

    if exclusive:
        check(
            f"{name}: нажатая «{label}» отмечена, и только она",
            after == [label],
            f"отмечены {after}, ждали ['{label}']",
        )
    else:
        check(
            f"{name}: слова «{label}» попали в поле и кнопка отмечена",
            label in after,
            f"отмечены {after}",
        )
        check(
            f"{name}: отмеченные раньше не потеряли отметку",
            set(before) <= set(after),
            f"было {before}, стало {after}",
        )


async def rows_of(pg):
    """The rows of choice buttons on the screen, once they have arrived.

    The screen title is there before the list is, so reading the rows right after the title appears
    finds nothing at all: the filter row of the documents arrives with the documents.
    """
    await pg.locator("[role=group]").first.wait_for(state="attached", timeout=10_000)
    await pg.wait_for_timeout(250)
    return await pg.locator("[role=group]").all()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        pid = await login(pg, "demo", "Рекс")
        made_docs: list[str] = []

        try:
            # Подготовка к визиту: у каждого пункта один ответ из двух.
            await pg.goto(BASE + f"/pets/{pid}/visit-prep")
            await wait_until(pg, lambda t: "К чему" in t or "Осмотр" in t)
            groups = await rows_of(pg)
            check("на подготовке к визиту есть строки выбора", len(groups) > 0, f"групп {len(groups)}")
            for g in groups[:2]:
                await check_row(pg, g, "подготовка к визиту")

            # Медкарта питомца: подсказки еды и условий жизни. Это слова в поле, а не один ответ.
            await pg.goto(BASE + f"/pets/{pid}/medical-profile")
            await wait_until(pg, lambda t: "Чем кормят" in t)
            groups = await rows_of(pg)
            check("в медкарте питомца есть строки подсказок", len(groups) > 0, f"групп {len(groups)}")
            for g in groups[:2]:
                await check_row(pg, g, "медкарта питомца", exclusive=False)

            # Запись о медкарте: быстрый выбор даты и повтор.
            await pg.goto(BASE + f"/pets/{pid}/medical-records/new")
            await wait_until(pg, lambda t: "Прививка" in t)
            await pg.get_by_text("Прививка", exact=True).first.click()
            await wait_until(pg, lambda t: "Сегодня" in t)
            groups = await rows_of(pg)
            check("в форме записи о медкарте есть строки выбора", len(groups) >= 2, f"групп {len(groups)}")
            for g in groups:
                await check_row(pg, g, (await g.get_attribute("aria-label")) or "строка")

            # Документы: фильтр рисуется от одиннадцати файлов и дальше, поэтому файлы добиваются.
            have = len(((await api(pg, "GET", f"/documents?pet_id={pid}"))["json"] or {}).get("documents") or [])
            need = max(0, 11 - have)
            made_docs = await pg.evaluate(MAKE_DOCS % TINY_PNG, [pid, need]) if need else []
            check(
                "документов хватает, чтобы появился фильтр",
                len(made_docs) == need,
                f"было {have}, добавлено {len(made_docs)} из {need}",
            )
            await pg.goto(BASE + "/documents")
            await wait_until(pg, lambda t: "Документы" in t)
            groups = await rows_of(pg)
            check(
                "в документах есть строка фильтра",
                len(groups) > 0,
                f"групп {len(groups)}, документов было {have}, добавлено {need}",
            )
            for g in groups:
                await check_row(pg, g, "фильтр документов")

            check("no horizontal scroll", await pg.evaluate("document.documentElement.scrollWidth - innerWidth") == 0)
        finally:
            for doc_id in made_docs:
                await api(pg, "DELETE", f"/documents/{doc_id}")
        await b.close()
    summary("отметки у кнопок выбора")


asyncio.run(main())
