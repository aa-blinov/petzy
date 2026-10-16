"""The wording of «Доступ для ассистентов»: the texts the owner asked for, and the house rules for interface text.

The labels of the areas and the days come from the service; the secret's warning is said in the form; a revoke asks
first. No middle dot and no long dash in these screens (CLAUDE.md, «Interface text»).
"""

from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
SCREENS = ["pages/AssistantAccess.tsx", "pages/AssistantAccessForm.tsx", "pages/AssistantAccess.css"]
SERVICE = "services/personalTokens.service.ts"


def _source(name: str) -> str:
    return (FRONTEND / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "label",
    ["Читать питомцев", "Записывать события", "Читать ленту и историю", "Читать медкарту"],
)
def test_each_area_is_named_as_the_owner_asked(label):
    assert f"'{label}'" in _source(SERVICE)


def test_the_expiry_offers_30_90_and_365_days():
    assert "TOKEN_DAYS = [30, 90, 365]" in _source(SERVICE)


def test_the_secret_is_said_to_be_shown_once():
    assert "Токен показывается один раз, сохраните его сейчас" in _source("pages/AssistantAccessForm.tsx")


def test_the_secret_has_a_copy_button():
    assert "Скопировать" in _source("pages/AssistantAccessForm.tsx")


def test_a_revoke_asks_first():
    list_page = _source("pages/AssistantAccess.tsx")
    assert "Dialog.confirm" in list_page
    assert "Отозвать доступ?" in list_page


def test_the_settings_row_opens_the_section():
    settings = _source("pages/Settings.tsx")
    assert "Доступ для ассистентов" in settings
    assert "navigate('/settings/assistants')" in settings


@pytest.mark.parametrize("name", SCREENS + [SERVICE])
def test_no_middle_dot_and_no_long_dash(name):
    source = _source(name)
    assert "·" not in source, name
    assert "—" not in source and "–" not in source, name
