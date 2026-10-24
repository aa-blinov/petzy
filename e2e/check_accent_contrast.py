"""What lands on a pet's colour has to be readable on every pet's colour.

A pet's look may replace the app's accent with any of seven, and the card carries that colour:
the round «+» of a block is painted in it. Checking the default alone is how a 4.481:1 pairing
ships with a claim of compliance in DESIGN.md: the default failed by a twentieth, and none of the
seven pet colours was the default.

The weight is read too, on the sheet under it: the card is strict, and its numbers stand in ink
rather than on a tinted chip.

Measured on rendered pixels, in both themes, on the card. The bar is 4.5:1, since the largest of
these is 16px at weight 700, below the 18.66px bold threshold for large text.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
from common import BASE, check, login, new_page, summary  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

MINIMUM = 4.5


def _luminance(colour: str) -> float:
    parts = [float(x) for x in __import__("re").findall(r"[\d.]+", colour)[:3]]
    channel = []
    for value in parts:
        value /= 255
        channel.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2]


def ratio(fore: str, back: str) -> float:
    a, b = _luminance(fore), _luminance(back)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# Every pet colour, walked on the real element rather than read from the stylesheet: the rule
# is about what a person sees on the card, and the seven accents are the ones that can be seen.
ACCENTS = ["", "sage", "sky", "lilac", "rose", "sun", "teal", "slate"]

# The weight stands in ink on the sheet of the passport, and the round «+» of a block is painted
# in the pet's own deep colour. Both are always there on the card.
ELEMENT = ".medcard__weight-chip"
ELEMENT_ACCENT = ".medcard__add"

APPLY = """
([accent, selector]) => {
  if (accent) document.body.setAttribute('data-pet-accent', accent);
  else document.body.removeAttribute('data-pet-accent');
  const el = document.querySelector(selector);
  if (!el) return null;
  // The ground the text stands on: the nearest ancestor that paints something. An element with
  // no ground of its own is read on the sheet under it.
  let node = el;
  let bg = 'rgba(0, 0, 0, 0)';
  // A round control may draw its disc in ::before (the box to press is larger than the disc): that disc is its ground.
  const before = getComputedStyle(el, '::before');
  if (before.content !== 'none' && before.backgroundColor !== 'rgba(0, 0, 0, 0)' && before.backgroundColor !== 'transparent') {
    return { fg: getComputedStyle(el).color, bg: before.backgroundColor };
  }
  while (node) {
    const colour = getComputedStyle(node).backgroundColor;
    if (colour && colour !== 'rgba(0, 0, 0, 0)' && colour !== 'transparent') {
      bg = colour;
      break;
    }
    node = node.parentElement;
  }
  return { fg: getComputedStyle(el).color, bg };
}
"""


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for dark in (False, True):
            ctx, pg = await new_page(browser, dark=dark)
            await login(pg, "demo", "Рекс")
            pet = await pg.evaluate("fetch('/api/pets').then(r=>r.json()).then(d=>d.pets.find(p=>p.name==='Рекс')._id)")
            await pg.goto(BASE + f"/pets/{pet}/medical-card")
            await pg.wait_for_selector(ELEMENT, timeout=20000)
            await pg.wait_for_timeout(900)
            for accent in ACCENTS:
                got = await pg.evaluate(APPLY, [accent, ELEMENT])
                if got is None:
                    check(
                        f"{'тёмная' if dark else 'светлая'} тема, цвет {accent or 'обычный'}",
                        False,
                        "вес не отрисован",
                    )
                    continue
                r = ratio(got["fg"], got["bg"])
                check(
                    f"{'тёмная' if dark else 'светлая'} тема, вес на цвете «{accent or 'обычном'}»",
                    r >= MINIMUM,
                    f"{r:.3f}:1 (нужно {MINIMUM}), {got['fg']} на {got['bg']}",
                )
                # The pet's own colour meets the card in the round «+» of a block.
                got = await pg.evaluate(APPLY, [accent, ELEMENT_ACCENT])
                if got is None:
                    check(
                        f"{'тёмная' if dark else 'светлая'} тема, «+» на цвете «{accent or 'обычном'}»",
                        False,
                        "кнопка не нарисована",
                    )
                    continue
                r = ratio(got["fg"], got["bg"])
                check(
                    f"{'тёмная' if dark else 'светлая'} тема, «+» на цвете «{accent or 'обычном'}»",
                    r >= MINIMUM,
                    f"{r:.3f}:1 (нужно {MINIMUM}), {got['fg']} на {got['bg']}",
                )
            await ctx.close()
        await browser.close()
    summary("text on a pet's colour reads in both themes")


asyncio.run(main())
