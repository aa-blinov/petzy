"""Small helpers for Russian text that several modules share (no imports from the app, so any module may use it)."""

import re

_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})", re.ASCII)
_TIME = re.compile(r"([01]\d|2[0-3]):([0-5]\d)", re.ASCII)


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    """The form of a noun that goes with the number: 1 день, 2 дня, 5 дней, 11 дней, 21 день."""
    mod10, mod100 = n % 10, n % 100
    if mod10 == 1 and mod100 != 11:
        return one
    if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        return few
    return many


BIRTH_FUTURE_TEXT = "Дата рождения не может быть в будущем"


def too_far_ahead_text(days: int) -> str:
    if days <= 0:
        return "Дата не может быть в будущем"
    return f"Дата не может быть более чем на {days} {plural_ru(days, 'день', 'дня', 'дней')} в будущем"


def too_far_back_text(years: int) -> str:
    return f"Дата не может быть более чем на {years} {plural_ru(years, 'год', 'года', 'лет')} в прошлом"


def is_strict_date(text) -> bool:
    """Exactly YYYY-MM-DD in ASCII digits. strptime alone also takes «2026-1-5», and dates are compared as text."""
    return isinstance(text, str) and _DATE.fullmatch(text) is not None


def is_strict_time(text) -> bool:
    """Exactly HH:MM in ASCII digits, a real clock time."""
    return isinstance(text, str) and _TIME.fullmatch(text) is not None
