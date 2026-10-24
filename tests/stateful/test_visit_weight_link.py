"""A visit points at the weighing that was said at it, and only at a weighing of its own pet."""

from datetime import datetime, timedelta, timezone

import pytest

TODAY = datetime.now(timezone.utc).date()
DAY = (TODAY - timedelta(days=1)).isoformat()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _weight(client, token, pet, value=6.6):
    answer = client.post(
        "/api/events",
        json={
            "pet_id": str(pet["_id"]),
            "type": "weight",
            "date": DAY,
            "time": "12:00",
            "fields": {"weight": value},
            "comment": "",
            "tz": "Asia/Almaty",
        },
        headers=_auth(token),
    )
    assert answer.status_code == 201, answer.get_json()
    return answer.get_json()["id"]


def _visit(client, token, pet, **extra):
    return client.post(
        "/api/medical-records",
        json={"pet_id": str(pet["_id"]), "kind": "visit", "date": DAY, "title": "Осмотр", **extra},
        headers=_auth(token),
    )


def _records(client, token, pet):
    return client.get(f"/api/medical-records?pet_id={pet['_id']}", headers=_auth(token)).get_json()["records"]


def test_a_visit_keeps_the_weighing_it_names(client, regular_user_token, test_pet):
    weight_id = _weight(client, regular_user_token, test_pet)

    made = _visit(client, regular_user_token, test_pet, weight_event_id=weight_id)

    assert made.status_code == 201, made.get_json()
    assert _records(client, regular_user_token, test_pet)[0]["weight_event_id"] == weight_id


def test_a_weighing_of_another_pet_is_refused(client, mock_db, regular_user_token, test_pet):
    other = mock_db.pets.insert_one({"name": "Чужой", "owner": "someone-else"}).inserted_id
    foreign = mock_db.events.insert_one({"pet_id": str(other), "type": "weight", "fields": {"weight": 4}}).inserted_id

    answer = _visit(client, regular_user_token, test_pet, weight_event_id=str(foreign))

    assert answer.status_code == 422
    assert "Запись веса" in answer.get_json()["error"]
    assert _records(client, regular_user_token, test_pet) == []


def test_an_event_that_is_not_a_weighing_is_refused(client, mock_db, regular_user_token, test_pet):
    feeding = mock_db.events.insert_one(
        {"pet_id": str(test_pet["_id"]), "type": "feeding", "fields": {"food_weight": 50}}
    ).inserted_id

    assert _visit(client, regular_user_token, test_pet, weight_event_id=str(feeding)).status_code == 422


def test_only_a_visit_keeps_the_link(client, regular_user_token, test_pet):
    weight_id = _weight(client, regular_user_token, test_pet)
    made = client.post(
        "/api/medical-records",
        json={
            "pet_id": str(test_pet["_id"]),
            "kind": "procedure",
            "date": DAY,
            "title": "Чистка зубов",
            "weight_event_id": weight_id,
        },
        headers=_auth(regular_user_token),
    )

    assert made.status_code == 201
    assert _records(client, regular_user_token, test_pet)[0]["weight_event_id"] is None


def test_an_edit_keeps_the_link_when_it_is_sent_and_clears_it_when_it_is_not(client, regular_user_token, test_pet):
    weight_id = _weight(client, regular_user_token, test_pet)
    record_id = _visit(client, regular_user_token, test_pet, weight_event_id=weight_id).get_json()["id"]
    body = {"date": DAY, "title": "Осмотр", "diagnosis": "Без патологии"}

    kept = client.put(
        f"/api/medical-records/{record_id}",
        json={**body, "weight_event_id": weight_id},
        headers=_auth(regular_user_token),
    )
    assert kept.status_code == 200, kept.get_json()
    assert _records(client, regular_user_token, test_pet)[0]["weight_event_id"] == weight_id

    cleared = client.put(f"/api/medical-records/{record_id}", json=body, headers=_auth(regular_user_token))
    assert cleared.status_code == 200
    assert _records(client, regular_user_token, test_pet)[0]["weight_event_id"] is None


@pytest.mark.parametrize("value", ["", "not-an-id"])
def test_a_bad_id_is_a_refusal_not_a_crash(client, regular_user_token, test_pet, value):
    answer = _visit(client, regular_user_token, test_pet, weight_event_id=value)

    assert answer.status_code in (422, 201)
    assert answer.status_code != 500
