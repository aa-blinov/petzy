"""An export shows the time on the clock of whoever exports.

A record stores the wall-clock time as it was entered, plus (when the app
sends it) the IANA zone of that clock. The export moves each time onto the
exporter's zone; a record without a zone is shown as stored.
"""

import csv
import io
from datetime import datetime

import pytest

from bson import ObjectId

from web.helpers import valid_tz, wall_clock_in


class TestZoneHelpers:
    @pytest.mark.parametrize("name", ["Asia/Almaty", "Europe/Moscow", "UTC"])
    def test_real_zones_are_kept(self, name):
        assert valid_tz(name) == name

    @pytest.mark.parametrize("name", [None, "", "Not/AZone", "../etc/passwd", 5, "x" * 80])
    def test_anything_else_is_dropped(self, name):
        assert valid_tz(name) is None

    def test_clock_moves_between_zones(self):
        noon = datetime(2026, 9, 30, 12, 0)
        assert wall_clock_in(noon, "Asia/Almaty", "Europe/Moscow") == datetime(2026, 9, 30, 10, 0)
        assert wall_clock_in(noon, "Europe/Moscow", "Asia/Almaty") == datetime(2026, 9, 30, 14, 0)

    def test_the_date_can_change(self):
        assert wall_clock_in(datetime(2026, 9, 30, 23, 30), "Asia/Almaty", "Europe/Moscow") == datetime(
            2026, 9, 30, 21, 30
        )
        assert wall_clock_in(datetime(2026, 9, 30, 1, 0), "Asia/Almaty", "Europe/Moscow") == datetime(
            2026, 9, 29, 23, 0
        )

    def test_daylight_saving_is_the_zones_own(self):
        # Berlin is UTC+1 in January, UTC+2 in July: the same 12:00 is 11:00 or 10:00 UTC
        assert wall_clock_in(datetime(2026, 1, 15, 12, 0), "Europe/Berlin", "UTC") == datetime(2026, 1, 15, 11, 0)
        assert wall_clock_in(datetime(2026, 7, 15, 12, 0), "Europe/Berlin", "UTC") == datetime(2026, 7, 15, 10, 0)

    @pytest.mark.parametrize(
        "source,target", [(None, "Asia/Almaty"), ("Asia/Almaty", None), ("Bad/Zone", "UTC"), ("UTC", "UTC")]
    )
    def test_unknown_or_same_zone_leaves_the_time_alone(self, source, target):
        noon = datetime(2026, 9, 30, 12, 0)
        assert wall_clock_in(noon, source, target) == noon


def _event(db, pet_id, when, comment, tz=None):
    doc = {
        "pet_id": pet_id,
        "type": "weight",
        "date_time": when,
        "fields": {"weight": 4.0},
        "comment": comment,
        "username": "u",
    }
    if tz:
        doc["tz"] = tz
    db["events"].insert_one(doc)


def _rows(client, token, pet, query):
    response = client.get(
        f"/api/export/weight/csv?pet_id={pet['_id']}{query}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    return {r[-1]: r[0] for r in list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))[1:]}


@pytest.mark.health
class TestExportOnTheExportersClock:
    def test_time_is_shown_on_the_exporters_clock(self, client, mock_db, regular_user_token, test_pet):
        _event(mock_db, str(test_pet["_id"]), datetime(2026, 9, 30, 12, 0), "almaty", tz="Asia/Almaty")
        _event(mock_db, str(test_pet["_id"]), datetime(2026, 9, 30, 12, 0), "moscow", tz="Europe/Moscow")

        for query, expected in [
            ("&tz=Europe/Moscow", {"almaty": "30.09.2026 10:00", "moscow": "30.09.2026 12:00"}),
            ("&tz=Asia/Almaty", {"almaty": "30.09.2026 12:00", "moscow": "30.09.2026 14:00"}),
            ("&tz=UTC", {"almaty": "30.09.2026 07:00", "moscow": "30.09.2026 09:00"}),
        ]:
            assert _rows(client, regular_user_token, test_pet, query) == expected

    def test_a_record_without_a_zone_is_shown_as_stored(self, client, mock_db, regular_user_token, test_pet):
        _event(mock_db, str(test_pet["_id"]), datetime(2026, 9, 30, 12, 0), "old")
        assert _rows(client, regular_user_token, test_pet, "&tz=Europe/Moscow") == {"old": "30.09.2026 12:00"}

    def test_without_an_exporter_zone_nothing_is_moved(self, client, mock_db, regular_user_token, test_pet):
        _event(mock_db, str(test_pet["_id"]), datetime(2026, 9, 30, 12, 0), "a", tz="Asia/Almaty")
        assert _rows(client, regular_user_token, test_pet, "") == {"a": "30.09.2026 12:00"}
        assert _rows(client, regular_user_token, test_pet, "&tz=Nope/Nope") == {"a": "30.09.2026 12:00"}

    def test_rows_are_newest_first_on_the_exporters_clock(self, client, mock_db, regular_user_token, test_pet):
        # Stored as a clock, 12:30 is later than 11:00; as instants (UTC) it is 07:30 against 08:00.
        _event(
            mock_db, str(test_pet["_id"]), datetime(2026, 9, 30, 11, 0), "moscow 11:00", tz="Europe/Moscow"
        )  # 08:00 UTC
        _event(
            mock_db, str(test_pet["_id"]), datetime(2026, 9, 30, 12, 30), "almaty 12:30", tz="Asia/Almaty"
        )  # 07:30 UTC
        response = client.get(
            f"/api/export/weight/csv?pet_id={test_pet['_id']}&tz=UTC",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        order = [r[-1] for r in list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))[1:]]
        assert order == ["moscow 11:00", "almaty 12:30"]  # by instant, although 12:30 > 11:00 as a stored clock


def _post_weight(client, token, pet, **extra):
    response = client.post(
        "/api/events",
        json={
            "pet_id": str(pet["_id"]),
            "type": "weight",
            "date": "2026-09-30",
            "time": "12:00",
            "fields": {"weight": 4.2},
            **extra,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response


@pytest.mark.health
class TestZoneIsStoredWithTheRecord:
    def test_created_record_keeps_a_valid_zone(self, client, mock_db, regular_user_token, test_pet):
        _post_weight(client, regular_user_token, test_pet, tz="Asia/Almaty")
        assert mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["tz"] == "Asia/Almaty"

    @pytest.mark.parametrize("extra", [{}, {"tz": "Not/AZone"}])
    def test_no_or_bad_zone_stores_none(self, client, mock_db, regular_user_token, test_pet, extra):
        _post_weight(client, regular_user_token, test_pet, **extra)
        assert "tz" not in mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})

    def test_editing_only_the_comment_keeps_the_authors_zone(self, client, mock_db, regular_user_token, test_pet):
        _post_weight(client, regular_user_token, test_pet, tz="Asia/Almaty")
        rid = str(mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["_id"])
        # the form sends the whole time back, from another zone, with the clock unchanged
        response = client.put(
            f"/api/events/{rid}",
            json={"date": "2026-09-30", "time": "12:00", "comment": "edited", "tz": "Europe/Moscow"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        assert (
            mock_db["events"].find_one({"_id": mock_db["events"].find_one({"comment": "edited"})["_id"]})["tz"]
            == "Asia/Almaty"
        )

    def test_moving_the_time_restamps_the_zone(self, client, mock_db, regular_user_token, test_pet):
        _post_weight(client, regular_user_token, test_pet, tz="Asia/Almaty")
        rid = str(mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["_id"])
        client.put(
            f"/api/events/{rid}",
            json={"date": "2026-09-30", "time": "13:00", "tz": "Europe/Moscow"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        doc = mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})
        assert (doc["date_time"].hour, doc["tz"]) == (13, "Europe/Moscow")


@pytest.mark.health
class TestIntakeZone:
    def _medication(self, mock_db, pet):
        med_id = ObjectId()
        mock_db["medications"].insert_one(
            {"_id": med_id, "pet_id": str(pet["_id"]), "name": "Vit", "inventory_enabled": False, "owner": "testuser"}
        )
        return str(med_id)

    def _log(self, client, token, med_id, **extra):
        response = client.post(
            f"/api/medications/{med_id}/log",
            json={"date": "2026-09-30", "time": "12:00", "dose_taken": 1.0, **extra},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        return response.get_json()["id"]

    def test_intake_keeps_its_zone_and_is_exported_on_the_exporters_clock(
        self, client, mock_db, regular_user_token, test_pet
    ):
        med_id = self._medication(mock_db, test_pet)
        self._log(client, regular_user_token, med_id, tz="Asia/Almaty")
        assert mock_db["medication_intakes"].find_one({})["tz"] == "Asia/Almaty"
        response = client.get(
            f"/api/export/medications/csv?pet_id={test_pet['_id']}&tz=Europe/Moscow",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
        assert rows[1][0] == "30.09.2026 10:00"

    def test_intake_without_a_zone_stores_none(self, client, mock_db, regular_user_token, test_pet):
        self._log(client, regular_user_token, self._medication(mock_db, test_pet))
        assert "tz" not in mock_db["medication_intakes"].find_one({})

    def test_moving_an_intake_restamps_only_when_the_clock_moves(self, client, mock_db, regular_user_token, test_pet):
        intake_id = self._log(client, regular_user_token, self._medication(mock_db, test_pet), tz="Asia/Almaty")
        headers = {"Authorization": f"Bearer {regular_user_token}"}

        client.put(
            f"/api/medications/intakes/{intake_id}",
            json={"date": "2026-09-30", "time": "12:00", "tz": "Europe/Moscow"},
            headers=headers,
        )
        assert mock_db["medication_intakes"].find_one({})["tz"] == "Asia/Almaty"

        client.put(
            f"/api/medications/intakes/{intake_id}",
            json={"date": "2026-09-30", "time": "13:00", "tz": "Europe/Moscow"},
            headers=headers,
        )
        assert mock_db["medication_intakes"].find_one({})["tz"] == "Europe/Moscow"
