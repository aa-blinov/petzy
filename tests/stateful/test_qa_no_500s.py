"""Input that used to end in a 500 is a 422 with a Russian message (QA B-09)."""

from datetime import datetime, timezone

import pytest
from bson import ObjectId


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def course(mock_db, test_pet):
    med_id = ObjectId()
    mock_db["medications"].insert_one(
        {
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Габапентин",
            "type": "Таблетка",
            "default_dose": 1.0,
            "is_active": True,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
            "created_at": datetime.now(timezone.utc),
        }
    )
    return med_id


FEEDS = ["/api/events", "/api/history/timeline"]
BAD_CURSORS = [
    "2026-13-45T25:61,64f1a2b3c4d5e6f708192a3b",
    "2026-02-30T10:00,64f1a2b3c4d5e6f708192a3b",
    "2026-10-18T24:00:00,64f1a2b3c4d5e6f708192a3b",
]


@pytest.mark.parametrize("path", FEEDS)
@pytest.mark.parametrize("cursor", BAD_CURSORS)
def test_an_impossible_feed_cursor_is_422(client, regular_user_token, test_pet, path, cursor):
    response = client.get(
        path, query_string={"pet_id": str(test_pet["_id"]), "before": cursor}, headers=_auth(regular_user_token)
    )
    assert response.status_code == 422
    assert "Курсор" in response.get_json()["error"]


@pytest.mark.parametrize("cursor", BAD_CURSORS)
def test_an_impossible_events_sync_cursor_is_422(client, regular_user_token, test_pet, cursor):
    response = client.get(
        "/api/events",
        query_string={"pet_id": str(test_pet["_id"]), "since": "2026-01-01T00:00:00Z", "after": cursor},
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "cursor",
    ["2026-13-45T25:61:00,pet,64f1a2b3c4d5e6f708192a3b", "2026-02-30T10:00:00,pet,64f1a2b3c4d5e6f708192a3b"],
)
def test_an_impossible_sync_cursor_is_422(client, regular_user_token, cursor):
    response = client.get("/api/sync", query_string={"after": cursor}, headers=_auth(regular_user_token))
    assert response.status_code == 422


@pytest.mark.parametrize("since", ["0001-01-01T00:00:00+05:00", "9999-12-31T23:59:59-05:00"])
def test_a_sync_moment_at_the_edge_of_the_calendar_is_422(client, regular_user_token, since):
    response = client.get("/api/sync", query_string={"since": since}, headers=_auth(regular_user_token))
    assert response.status_code == 422


@pytest.mark.parametrize("path", ["/api/events", "/api/history/timeline", "/api/documents", "/api/medications/intakes"])
def test_a_page_near_int64_is_422_not_500(client, regular_user_token, test_pet, path):
    response = client.get(
        path,
        query_string={"pet_id": str(test_pet["_id"]), "page": 9223372036854775807},
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422


@pytest.mark.parametrize("moment", ["0001-01-01T00:00:00Z", "9999-12-31T23:59:59Z", "9999-12-31T23:59:59-05:00"])
def test_upcoming_doses_with_a_moment_at_the_edge_of_the_calendar_is_422(
    client, regular_user_token, test_pet, course, moment
):
    response = client.get(
        "/api/medications/upcoming",
        query_string={"pet_id": str(test_pet["_id"]), "client_datetime": moment},
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422


@pytest.mark.parametrize("slot_date", ["9999-99-99", "2026-02-30", "0001-01-01", "9999-12-31"])
def test_a_log_with_an_impossible_slot_date_is_422(client, mock_db, regular_user_token, course, slot_date):
    now = datetime.now()
    response = client.post(
        f"/api/medications/{course}/log",
        json={
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "slot_date": slot_date,
            "slot_time": "08:00",
            "tz": "Asia/Almaty",
        },
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422
    assert mock_db["medication_intakes"].count_documents({}) == 0


def test_a_dose_that_is_astronomically_large_is_422(client, mock_db, regular_user_token, course):
    now = datetime.now()
    response = client.post(
        f"/api/medications/{course}/log",
        json={
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "dose_taken": 1e308,
            "tz": "Asia/Almaty",
        },
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422
