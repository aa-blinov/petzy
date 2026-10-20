"""The wording of the contract for the native app: what a full read asks for.

The app reads the feed with `GET /api/events?...&before=…` and without `with_deleted=1`,
because tombstones took up room in the page and left the feed looking empty. The contract
used to tell the app to read the full feed with `with_deleted=1`, which sent it back to
tombstones. The rule is checked here so the text is not quietly turned back.
"""

from pathlib import Path

import pytest

CONTRACT = Path(__file__).resolve().parents[2] / "web" / "openapi_doc.py"


def _point(number: str) -> str:
    """The line of the contract that starts the numbered point."""
    line = next(line for line in _CONTRACT.read_text(encoding="utf-8").splitlines() if line.startswith(f"{number}. "))
    return line


_CONTRACT = CONTRACT


@pytest.mark.health
class TestTheContractForTheNativeApp:
    def test_the_full_read_is_asked_for_without_the_tombstones(self):
        point = _point("6")
        assert "`GET /api/events?pet_id=…&page_size=500`" in point
        # The flag in the request itself: the old text told the app to read the full feed with
        # the tombstones in it, and the tombstones took up room in the page.
        assert "with_deleted=1&page_size" not in point
        assert "Полная лента: `GET /api/events?pet_id=…&with_deleted=1" not in point

    def test_the_contract_says_the_ordinary_answer_gives_the_live_records_only(self):
        point = _point("6")
        assert "без `with_deleted=1`, отдаёт только живые записи" in point
        assert "для полного чтения с заменой локальной копии этого достаточно" in point

    def test_the_contract_says_the_tombstones_are_for_the_client_that_syncs_by_since(self):
        point = _point("6")
        assert "Надгробия нужны клиенту, который обновляется по `since`" in point

    def test_the_contract_says_the_cursor_counts_the_live_records(self):
        point = _point("6")
        assert "Курсор считается по живым записям" in point
        assert "без пропусков и повторов" in point
