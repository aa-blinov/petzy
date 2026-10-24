"""The clinics and doctors a record's form offers are every one the person already named, not the last few of one pet."""

from datetime import datetime, timezone


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _record(mock_db, pet, day, clinic, vet=None):
    mock_db.medical_records.insert_one(
        {
            "pet_id": str(pet["_id"]),
            "kind": "vaccination",
            "title": "Нобивак",
            "date": day,
            "clinic": clinic,
            "vet": vet,
        }
    )


def _places(client, token):
    answer = client.get("/api/medical-records/places", headers=_auth(token))
    assert answer.status_code == 200, answer.get_json()
    return answer.get_json()


def test_clinics_beyond_the_last_ten_records_are_offered(client, mock_db, regular_user_token, test_pet):
    for i in range(1, 13):
        _record(mock_db, test_pet, f"2026-01-{i:02d}", f"Клиника {i}", f"Врач {i}")

    places = _places(client, regular_user_token)

    assert len(places["clinics"]) == 12
    assert len(places["doctors"]) == 12
    assert places["clinics"][0] == "Клиника 12"  # the most recent use first
    assert {"name": "Врач 1", "clinic": "Клиника 1"} in places["doctors"]


def test_a_clinic_named_for_another_pet_of_the_person_is_offered(
    client, mock_db, regular_user, regular_user_token, test_pet
):
    other = mock_db.pets.insert_one(
        {
            "name": "Второй",
            "owner": regular_user["username"],
            "shared_with": [],
            "created_at": datetime.now(timezone.utc),
        }
    ).inserted_id
    _record(mock_db, {"_id": other}, "2026-03-01", "Лапка", "Петров П.П.")

    places = _places(client, regular_user_token)

    assert "Лапка" in places["clinics"]
    assert {"name": "Петров П.П.", "clinic": "Лапка"} in places["doctors"]


def test_a_pet_of_somebody_else_is_not_read(client, mock_db, regular_user_token, test_pet):
    stranger = mock_db.pets.insert_one({"name": "Чужой", "owner": "someone-else", "shared_with": []}).inserted_id
    _record(mock_db, {"_id": stranger}, "2026-03-01", "Чужая клиника", "Чужой врач")

    places = _places(client, regular_user_token)

    assert "Чужая клиника" not in places["clinics"]
    assert all(d["name"] != "Чужой врач" for d in places["doctors"])


def test_a_pet_shared_with_the_person_is_read(client, mock_db, regular_user, regular_user_token, test_pet):
    shared = mock_db.pets.insert_one(
        {"name": "Общий", "owner": "someone-else", "shared_with": [regular_user["username"]]}
    ).inserted_id
    _record(mock_db, {"_id": shared}, "2026-03-01", "Семейная клиника")

    assert "Семейная клиника" in _places(client, regular_user_token)["clinics"]


def test_the_profile_clinics_and_doctors_are_offered_once_whatever_the_case(
    client, mock_db, regular_user_token, test_pet
):
    mock_db.pets.update_one(
        {"_id": test_pet["_id"]},
        {"$set": {"medical_profile": {"clinics": [{"name": "Айболит", "doctors": [{"name": "Иванова И.И."}]}]}}},
    )
    _record(mock_db, test_pet, "2026-02-01", " айболит ", "иванова и.и.")

    places = _places(client, regular_user_token)

    assert [c.lower() for c in places["clinics"]].count("айболит") == 1
    assert [d["name"].lower() for d in places["doctors"]].count("иванова и.и.") == 1


def test_it_needs_a_sign_in(client):
    assert client.get("/api/medical-records/places").status_code == 401
