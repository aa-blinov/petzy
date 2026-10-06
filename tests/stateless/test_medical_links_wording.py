"""The wording of the link settings: it is about shared links anyone with access to the pet may use, not about
links the person handed out. The old text («Кому вы дали доступ») said the opposite, so the rule is checked here."""

from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _source(name: str) -> str:
    return (FRONTEND / "pages" / name).read_text(encoding="utf-8")


@pytest.mark.health
class TestTheLinkSettingsWording:
    def test_the_settings_row_says_the_links_are_shared(self):
        settings = _source("Settings.tsx")
        assert "Общие ссылки на медкарты" in settings
        # The old text said the links were the person's own: «Кому вы дали доступ к карте».
        assert "Кому вы дали доступ" not in settings

    def test_the_row_says_who_may_use_them(self):
        settings = _source("Settings.tsx")
        row = next(line for line in settings.splitlines() if "Общие ссылки на медкарты" in line)
        assert "любой, у кого есть доступ к питомцу" in row

    def test_the_page_says_a_link_is_opened_by_anyone_who_has_it(self):
        links = _source("MedicalLinks.tsx")
        assert "Общие ссылки на медкарты" in links
        assert "без входа в приложение" in links
        assert "отозвать любую может любой, у кого есть доступ к питомцу" in links

    def test_the_new_lines_follow_the_house_style(self):
        """No «·», no long dash outside a range, and a line of interface text ends without a period."""
        for name in ("Settings.tsx", "MedicalLinks.tsx"):
            for line in _source(name).splitlines():
                if "Общие ссылки" not in line and "отозвать любую может любой" not in line:
                    continue
                assert "·" not in line, name
                assert "—" not in line and "–" not in line, name
                assert not line.rstrip().endswith((".", ",")), name
