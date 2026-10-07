"""The dose unit reaches a person in Russian, whatever the course was written with.

A course may carry «tablet» from a script or an older client. Every place that shows a dose —
the medication list and card, the feed, the medical card and its PDF — reads it as «таб», and the
stored value is left exactly as it was, so nothing is rewritten behind the owner's back.
"""

from datetime import datetime, timezone

from bson import ObjectId


def _course(mock_db, pet, unit, dose=1):
    medication_id = ObjectId()
    mock_db["medications"].insert_one(
        {
            "_id": medication_id,
            "pet_id": str(pet["_id"]),
            "name": "Антибиотик",
            "type": "pill",
            "default_dose": dose,
            "dose_unit": unit,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
            "inventory_enabled": False,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "owner": "testuser",
        }
    )
    return medication_id


class TestDoseUnitIsShownInRussian:
    def test_the_list_reads_an_english_unit_in_russian(self, client, mock_db, regular_user_token, test_pet):
        _course(mock_db, test_pet, "tablet")

        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.get_json()["medications"][0]["dose_unit"] == "таб"

    def test_the_card_of_one_course_reads_it_in_russian(self, client, mock_db, regular_user_token, test_pet):
        medication_id = _course(mock_db, test_pet, "tablets")

        response = client.get(
            f"/api/medications/{medication_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.get_json()["medication"]["dose_unit"] == "таб"

    def test_the_medical_card_reads_it_in_russian(self, client, mock_db, regular_user_token, test_pet):
        _course(mock_db, test_pet, "tablet")

        response = client.get(
            f"/api/pets/{test_pet['_id']}/medical-card",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        medications = response.get_json()["card"]["medications"]
        assert medications[0]["dose_text"] == "1 таб"

    def test_the_course_keeps_what_was_written(self, client, mock_db, regular_user_token, test_pet):
        # Reading is translated, storage is not: a course written by a script stays as it was,
        # and whoever owns it still sees their own word if it is ever exported.
        medication_id = _course(mock_db, test_pet, "tablet")

        client.get(
            f"/api/medications?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        stored = mock_db["medications"].find_one({"_id": medication_id})
        assert stored["dose_unit"] == "tablet"
