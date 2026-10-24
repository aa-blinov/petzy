"""A dose marked or a pack added moves the stock, not the course's version, so a device editing the course is not refused (QA B-23)."""

from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def course(client, mock_db, regular_user_token, test_pet):
    response = client.post(
        "/api/medications",
        json={
            "pet_id": str(test_pet["_id"]),
            "name": "Дронтал",
            "type": "Таблетка",
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
            "inventory_enabled": True,
            "inventory_total": 30,
            "inventory_current": 10,
        },
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 201, response.get_json()
    med_id = response.get_json()["id"]
    # Written an hour ago, so a later stamp is told apart from this one.
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    mock_db["medications"].update_one({"_id": ObjectId(med_id)}, {"$set": {"updated_at": old}})
    return med_id


def _version(client, token, med_id):
    return client.get(f"/api/medications/{med_id}", headers=_auth(token)).get_json()["medication"]["updated_at"]


def _edit(client, token, med_id, version):
    return client.put(
        f"/api/medications/{med_id}", json={"comment": "правка", "base_version": version}, headers=_auth(token)
    )


def _mark_dose(client, token, med_id):
    now = datetime.now()
    return client.post(
        f"/api/medications/{med_id}/log",
        json={"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M"), "tz": "Asia/Almaty"},
        headers=_auth(token),
    )


def test_marking_a_dose_does_not_conflict_a_device_editing_the_course(client, mock_db, regular_user_token, course):
    version = _version(client, regular_user_token, course)
    assert _mark_dose(client, regular_user_token, course).status_code == 201
    assert mock_db["medications"].find_one({"_id": ObjectId(course)})["inventory_current"] == 9
    assert _version(client, regular_user_token, course) == version
    assert _edit(client, regular_user_token, course, version).status_code == 200


def test_adding_a_pack_does_not_conflict_a_device_editing_the_course(client, regular_user_token, course):
    version = _version(client, regular_user_token, course)
    response = client.post(f"/api/medications/{course}/restock", json={"amount": 5}, headers=_auth(regular_user_token))
    assert response.status_code == 200
    assert _version(client, regular_user_token, course) == version
    assert _edit(client, regular_user_token, course, version).status_code == 200


def test_taking_back_a_dose_does_not_conflict_either(client, regular_user_token, course):
    intake_id = _mark_dose(client, regular_user_token, course).get_json()["id"]
    version = _version(client, regular_user_token, course)
    assert client.delete(f"/api/medications/intakes/{intake_id}", headers=_auth(regular_user_token)).status_code == 200
    assert _version(client, regular_user_token, course) == version
    assert _edit(client, regular_user_token, course, version).status_code == 200


def test_a_real_edit_still_conflicts_a_stale_copy(client, regular_user_token, course):
    version = _version(client, regular_user_token, course)
    assert _edit(client, regular_user_token, course, version).status_code == 200
    # The same stale copy again: someone changed the course since, so it is refused.
    assert _edit(client, regular_user_token, course, version).status_code == 409


def test_the_feed_still_reports_a_stock_change(client, mock_db, regular_user_token, course):
    """The version stays put, but a device following /api/sync is told the course moved (its stock did)."""
    old = mock_db["medications"].find_one({"_id": ObjectId(course)})["updated_at"]
    assert _mark_dose(client, regular_user_token, course).status_code == 201
    assert mock_db["medications"].find_one({"_id": ObjectId(course)})["updated_at"] > old
