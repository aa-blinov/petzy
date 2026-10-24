"""Saving the medical profile or the visit note moves the pet's own stamp, so /api/sync tells devices (QA B-07)."""

from datetime import datetime, timedelta, timezone

import pytest


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _old_stamp(mock_db, pet):
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)
    mock_db.pets.update_one({"_id": pet["_id"]}, {"$set": {"updated_at": old}})
    return old


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("medical-profile", {"diet": "Сухой корм"}),
        ("visit-prep", {"complaint": "Кашель", "checks": {}}),
    ],
)
def test_the_save_moves_the_pets_updated_at(client, mock_db, regular_user_token, test_pet, path, body):
    old = _old_stamp(mock_db, test_pet)
    response = client.put(f"/api/pets/{test_pet['_id']}/{path}", json=body, headers=_auth(regular_user_token))
    assert response.status_code == 200
    assert mock_db.pets.find_one({"_id": test_pet["_id"]})["updated_at"] > old

    since = (old + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    feed = client.get("/api/sync", query_string={"since": since}, headers=_auth(regular_user_token)).get_json()
    assert [(i["kind"], i["id"]) for i in feed["items"]] == [("pet", str(test_pet["_id"]))]


def test_clearing_the_visit_note_moves_the_stamp_too(client, mock_db, regular_user_token, test_pet):
    client.put(
        f"/api/pets/{test_pet['_id']}/visit-prep",
        json={"complaint": "Кашель", "checks": {}},
        headers=_auth(regular_user_token),
    )
    old = _old_stamp(mock_db, test_pet)
    response = client.put(
        f"/api/pets/{test_pet['_id']}/visit-prep",
        json={"complaint": "", "checks": {}},
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 200
    assert mock_db.pets.find_one({"_id": test_pet["_id"]})["updated_at"] > old
