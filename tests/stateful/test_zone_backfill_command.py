"""The zone a record gets, and the command that gives it (web/zone_backfill.py).

``python -m web.zone_backfill`` counts what ``--apply`` would write and writes nothing: a repair of the
records saved before a zone was kept must not change anything until the person asks for it
"""

import runpy
import sys
from datetime import datetime
from pathlib import Path

import pytest

import web.zone_backfill
from web.zone_backfill import backfill_zones, main

WHEN = datetime(2026, 10, 1, 9, 30)


def _pet(mock_db, owner):
    return mock_db["pets"].insert_one({"name": "Мурка", "owner": owner}).inserted_id


def _event(mock_db, pet, username, tz=None):
    row = {"pet_id": str(pet), "type": "weight", "date_time": WHEN, "username": username}
    if tz is not None:
        row["tz"] = tz
    return mock_db["events"].insert_one(row).inserted_id


class TestAZoneThatIsNotAName:
    @pytest.mark.parametrize("zone", [123, ""])
    def test_a_zone_that_is_not_a_name_at_all_leaves_the_records_alone(self, mock_db, zone):
        """A zone the zone database does not know names no zone (the other test covers a name it does not
        know). A zone that is not a name either, or an empty one, names none as well, and the repair goes on
        instead of falling over."""
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz=zone)
        legacy = _event(mock_db, pet, "vera")

        report = backfill_zones(mock_db, apply=True)

        assert "tz" not in mock_db["events"].find_one({"_id": legacy})
        assert report["events"]["unbound"] == 1 and report["events"]["written"] == 0


class TestTheCommand:
    def test_it_counts_and_writes_nothing(self, mock_db, monkeypatch, capsys):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        legacy = _event(mock_db, pet, "vera")
        monkeypatch.setattr(sys, "argv", ["zone_backfill"])

        main()

        out = capsys.readouterr().out
        assert "events: без пояса 1, пояс автора есть 1, не привязать 0" in out
        assert "Ничего не записано" in out
        assert "tz" not in mock_db["events"].find_one({"_id": legacy})

    def test_with_apply_it_writes_the_zones_and_says_how_many(self, mock_db, monkeypatch, capsys):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        legacy = _event(mock_db, pet, "vera")
        unbound = _event(mock_db, pet, "oleg")
        monkeypatch.setattr(sys, "argv", ["zone_backfill", "--apply"])

        main()

        out = capsys.readouterr().out
        assert "events: без пояса 2, пояс автора есть 1, не привязать 1, записано 1" in out
        assert "Ничего не записано" not in out
        assert mock_db["events"].find_one({"_id": legacy})["tz"] == "Asia/Almaty"
        assert "tz" not in mock_db["events"].find_one({"_id": unbound})

    def test_the_module_runs_as_the_documented_command(self, mock_db, monkeypatch, capsys):
        """``python -m web.zone_backfill`` is how the repair is run: the module has to answer to that name."""
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        _event(mock_db, pet, "vera")
        monkeypatch.setattr(sys, "argv", ["zone_backfill"])

        runpy.run_path(str(Path(web.zone_backfill.__file__)), run_name="__main__")

        assert "Ничего не записано" in capsys.readouterr().out
