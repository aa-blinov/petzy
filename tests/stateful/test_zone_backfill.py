"""Binding the records saved before a zone was kept to the zone of the person who saved them (web/zone_backfill.py)."""

from datetime import datetime

from web.zone_backfill import backfill_zones

WHEN = datetime(2026, 10, 1, 9, 30)


def _pet(mock_db, owner, tz=None):
    pet = {"name": "Мурка", "owner": owner}
    if tz is not None:
        pet["tz"] = tz
    return mock_db["pets"].insert_one(pet).inserted_id


def _event(mock_db, pet, username, tz=None):
    row = {
        "pet_id": str(pet),
        "type": "weight",
        "date_time": WHEN,
        "username": username,
    }  # kept as text, as the app writes it
    if tz is not None:
        row["tz"] = tz
    return mock_db["events"].insert_one(row).inserted_id


class TestTheZoneOfTheAuthor:
    def test_a_record_without_a_zone_takes_its_authors_zone(self, mock_db):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        legacy = _event(mock_db, pet, "vera")

        report = backfill_zones(mock_db, apply=True)

        assert mock_db["events"].find_one({"_id": legacy})["tz"] == "Asia/Almaty"
        assert report["events"]["written"] == 1

    def test_a_record_keeps_the_zone_it_already_has(self, mock_db):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        moscow = _event(mock_db, pet, "vera", tz="Europe/Moscow")

        backfill_zones(mock_db, apply=True)

        assert mock_db["events"].find_one({"_id": moscow})["tz"] == "Europe/Moscow"

    def test_the_zone_most_of_the_authors_records_name_is_the_one_taken(self, mock_db):
        pet = _pet(mock_db, "vera")
        for _ in range(3):
            _event(mock_db, pet, "vera", tz="Asia/Almaty")
        _event(mock_db, pet, "vera", tz="Europe/Moscow")
        legacy = _event(mock_db, pet, "vera")

        backfill_zones(mock_db, apply=True)

        assert mock_db["events"].find_one({"_id": legacy})["tz"] == "Asia/Almaty"

    def test_two_zones_named_equally_bind_nothing(self, mock_db):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        _event(mock_db, pet, "vera", tz="Europe/Moscow")
        legacy = _event(mock_db, pet, "vera")

        report = backfill_zones(mock_db, apply=True)

        assert "tz" not in mock_db["events"].find_one({"_id": legacy})
        assert report["events"]["unbound"] == 1

    def test_an_author_with_no_zoned_record_leaves_records_alone(self, mock_db):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        oleg = _event(mock_db, pet, "oleg")

        report = backfill_zones(mock_db, apply=True)

        assert "tz" not in mock_db["events"].find_one({"_id": oleg})
        assert report["events"]["unbound"] == 1 and report["events"]["written"] == 0

    def test_a_pets_zone_is_not_the_source(self, mock_db):
        pet = _pet(mock_db, "vera", tz="Asia/Almaty")
        legacy = _event(mock_db, pet, "oleg")

        backfill_zones(mock_db, apply=True)

        assert "tz" not in mock_db["events"].find_one({"_id": legacy})

    def test_a_zone_the_zone_database_does_not_know_is_not_bound(self, mock_db):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Mars/Olympus")
        legacy = _event(mock_db, pet, "vera")

        backfill_zones(mock_db, apply=True)

        assert "tz" not in mock_db["events"].find_one({"_id": legacy})

    def test_a_record_without_an_author_is_not_bound(self, mock_db):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, None, tz="Asia/Almaty")
        legacy = _event(mock_db, pet, None)

        backfill_zones(mock_db, apply=True)

        assert "tz" not in mock_db["events"].find_one({"_id": legacy})

    def test_without_apply_only_the_counts_come_back(self, mock_db):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        legacy = _event(mock_db, pet, "vera")

        report = backfill_zones(mock_db, apply=False)

        assert "tz" not in mock_db["events"].find_one({"_id": legacy})
        assert report["events"]["bindable"] == 1 and report["events"]["written"] == 0

    def test_a_second_run_writes_nothing(self, mock_db):
        pet = _pet(mock_db, "vera")
        _event(mock_db, pet, "vera", tz="Asia/Almaty")
        _event(mock_db, pet, "vera")
        backfill_zones(mock_db, apply=True)

        again = backfill_zones(mock_db, apply=True)

        assert again["events"]["without_zone"] == 0 and again["events"]["written"] == 0

    def test_an_authors_intakes_and_events_count_together(self, mock_db):
        pet = _pet(mock_db, "vera")
        mock_db["medication_intakes"].insert_one(
            {"pet_id": str(pet), "medication_id": "x", "date_time": WHEN, "username": "vera", "tz": "Asia/Almaty"}
        )
        legacy_event = _event(mock_db, pet, "vera")
        legacy_intake = (
            mock_db["medication_intakes"]
            .insert_one({"pet_id": str(pet), "medication_id": "x", "date_time": WHEN, "username": "vera"})
            .inserted_id
        )

        backfill_zones(mock_db, apply=True)

        assert mock_db["events"].find_one({"_id": legacy_event})["tz"] == "Asia/Almaty"
        assert mock_db["medication_intakes"].find_one({"_id": legacy_intake})["tz"] == "Asia/Almaty"

    def test_the_feed_shows_the_bound_zone(self, client, mock_db, regular_user, regular_user_token):
        name = regular_user["username"]
        other_pet = _pet(mock_db, name)
        _event(mock_db, other_pet, name, tz="Asia/Almaty")
        pet = _pet(mock_db, name)
        _event(mock_db, pet, name)
        backfill_zones(mock_db, apply=True)

        feed = client.get(f"/api/events?pet_id={pet}", headers={"Authorization": f"Bearer {regular_user_token}"})

        [item] = feed.get_json()["items"]
        assert item["tz"] == "Asia/Almaty"
        assert item["date_time"] == "2026-10-01T09:30:00+05:00"
