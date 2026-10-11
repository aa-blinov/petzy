"""Every name the help puts in « » has to exist in the app.

The help opens with the rule that a name in « » is the exact text on screen, so a button that was
renamed and a help page that still calls it the old name cannot both be right. That is not a
guess: the help described a medical card mode called «Сводка» that never existed, promised that
the reading view was remembered per pet when the code deliberately does not, and listed a «Лекарства
и вес» section under «Врачу» that has never been on screen, while leaving out «Здоровье и аллергии»
that is always first there.

So this check takes every « » out of the help and looks for it in the source: the front end, the
backend and the reminder script, since a push title is written in Python. What is left is a list
with a reason attached, so the exceptions stay deliberate instead of becoming a pile.

Reads files only: no browser, no stack, no demo data.
"""

import re
from pathlib import Path

from common import check, summary

ROOT = Path(__file__).resolve().parents[1]
HELP = ROOT / "frontend" / "src" / "content" / "help.ts"
SOURCE_DIRS = ("frontend/src", "web", "scripts")
SOURCE_SUFFIXES = (".ts", ".tsx", ".py")
# Demo content, not interface: names may sit inside a sentence of a seeded record.
DEMO_DATA = {"seed_demo.py", "seed_medical.py"}

# Names that are not the text of a control, and why each one is allowed to differ.
ALLOWED = {
    "Дали вовремя, в 08:00": "the button reads «Дали вовремя, в {time}», the help shows one clock",
    "Документах": "an inflected mention of the «Документы» tab in a sentence, not the name itself",
    "Моих питомцах": "an inflected mention of the «Мои питомцы» page in a sentence, not the name itself",
    "Частых вопросах": "an inflected mention of the «Частые вопросы» heading in a sentence",
    "Что такое медкарта и как показать её врачу?": "a question of the help itself, not a control",
}


def source() -> str:
    """The whole source, less the demo data.

    Substrings are matched, because many names are not a literal of their own: a button reads
    «Дали{...}», a title sits in JSX text, a push title is built with a format. That is loose
    enough on its own, so the demo data is left out: the help describes the interface, and seed
    data is not interface. «Профилактика» survived in there as «Профилактика глистов», a purpose
    of a treatment, and was enough to hide a help page still using the name the section lost.
    """
    parts = []
    for folder in SOURCE_DIRS:
        for path in (ROOT / folder).rglob("*"):
            if path.suffix in SOURCE_SUFFIXES and path != HELP and path.name not in DEMO_DATA:
                try:
                    parts.append(path.read_text())
                except (OSError, UnicodeDecodeError):
                    pass
    return "\n".join(parts)


def main() -> int:
    labels = sorted(set(re.findall(r"«([^»]{2,60})»", HELP.read_text())))
    blob = source()

    found = [label for label in labels if label in blob]
    missing = [label for label in labels if label not in blob and label not in ALLOWED]

    check(
        f"the help's {len(labels)} names are all still on screen",
        not missing,
        "; ".join(missing)[:300] if missing else f"{len(found)} found in the source",
    )
    for label in missing:
        print(f"      нет в коде: «{label}»")
    for label, why in ALLOWED.items():
        check(f"the exception «{label}» is still needed", label not in blob, why)

    stale = [label for label, why in ALLOWED.items() if label not in labels]
    check(
        "no exception outlived the name it was made for",
        not stale,
        f"these no longer appear in the help: {', '.join(stale)}"
        if stale
        else f"{len(ALLOWED)} exceptions, all in use",
    )
    summary("the help and the screen agree on names")


main()
