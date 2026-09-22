"""Tests for the timeline endpoint (now backed by `events` + `medication_intakes`)."""

import pytest
from datetime import datetime, timezone, timedelta
from bson import ObjectId


@pytest.mark.health
class TestTimeline:
    """Test timeline endpoint."""

    def test_get_timeline_requires_authentication(self, client):
        response = client.get("/api/history/timeline?pet_id=" + str(ObjectId()))
        assert response.status_code == 401

    def test_get_timeline_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting timeline records."""
        pet_id = str(test_pet["_id"])

        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "weight",
            "date_time": datetime.now(timezone.utc) - timedelta(hours=1),
            "fields": {"weight": 5.0}, "comment": "", "username": "testuser",
        })
        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "asthma",
            "date_time": datetime.now(timezone.utc),
            "fields": {}, "comment": "", "username": "testuser",
        })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "items" in data
        assert len(data["items"]) == 2
        # Check sorting (descending by date)
        assert data["items"][0]["record_type"] == "asthma"
        assert data["items"][1]["record_type"] == "weight"

    def test_get_timeline_includes_medications(self, client, mock_db, regular_user_token, test_pet):
        """Medications aren't part of the events collection but still show up."""
        pet_id = str(test_pet["_id"])
        med = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Vitamin C", "username": "testuser"})
        mock_db["medication_intakes"].insert_one({
            "pet_id": pet_id, "medication_id": str(med.inserted_id),
            "date_time": datetime.now(timezone.utc), "dose_taken": "1", "username": "testuser",
        })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["record_type"] == "medications"
        assert items[0]["medication_name"] == "Vitamin C"

    def test_get_timeline_resolves_distinct_medication_names(self, client, mock_db, regular_user_token, test_pet):
        """Each intake's medication_name matches its OWN medication.

        Names are batch-resolved with one `$in` query instead of a
        `find_one` per intake — this pins down that the batch lookup
        keeps each intake mapped to the right medication rather than,
        say, collapsing them all to whichever one was fetched last.
        """
        pet_id = str(test_pet["_id"])
        med_a = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Vitamin C", "username": "testuser"})
        med_b = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Antibiotic", "username": "testuser"})
        mock_db["medication_intakes"].insert_one({
            "pet_id": pet_id, "medication_id": str(med_a.inserted_id),
            "date_time": datetime.now(timezone.utc), "dose_taken": "1", "username": "testuser",
        })
        mock_db["medication_intakes"].insert_one({
            "pet_id": pet_id, "medication_id": str(med_b.inserted_id),
            "date_time": datetime.now(timezone.utc) - timedelta(minutes=1), "dose_taken": "1", "username": "testuser",
        })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        names_by_medication_id = {item["medication_id"]: item["medication_name"] for item in items}
        assert names_by_medication_id[str(med_a.inserted_id)] == "Vitamin C"
        assert names_by_medication_id[str(med_b.inserted_id)] == "Antibiotic"

    def test_get_timeline_filtering(self, client, mock_db, regular_user_token, test_pet):
        """Test getting timeline records with type filtering."""
        pet_id = str(test_pet["_id"])

        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "weight",
            "date_time": datetime.now(timezone.utc) - timedelta(hours=1),
            "fields": {"weight": 5.0}, "comment": "", "username": "testuser",
        })
        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "asthma",
            "date_time": datetime.now(timezone.utc),
            "fields": {}, "comment": "", "username": "testuser",
        })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&type=weight",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["record_type"] == "weight"

    def test_get_timeline_filtering_medications_excludes_events(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "weight", "date_time": datetime.now(timezone.utc),
            "fields": {"weight": 5.0}, "comment": "", "username": "testuser",
        })
        med = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Vitamin C", "username": "testuser"})
        mock_db["medication_intakes"].insert_one({
            "pet_id": pet_id, "medication_id": str(med.inserted_id),
            "date_time": datetime.now(timezone.utc), "dose_taken": "1", "username": "testuser",
        })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&type=medications",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["record_type"] == "medications"

    def test_get_timeline_pagination(self, client, mock_db, regular_user_token, test_pet):
        """Test timeline pagination."""
        pet_id = str(test_pet["_id"])

        for i in range(5):
            mock_db["events"].insert_one({
                "pet_id": pet_id, "type": "asthma",
                "date_time": datetime.now(timezone.utc) - timedelta(minutes=i),
                "fields": {}, "comment": "", "username": "testuser",
            })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&page=1&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["total"] == 5
        assert data["page"] * data["page_size"] < data["total"]

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&page=3&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["page"] == 3
        assert data["page"] * data["page_size"] >= data["total"]

    def test_get_timeline_pagination_across_mixed_sources(self, client, mock_db, regular_user_token, test_pet):
        """Pagination stays correct when events and medication intakes interleave.

        The handler fetches only the top `offset + page_size` from each
        source collection rather than everything, then merges and slices.
        Interleaving the two sources' timestamps here exercises that the
        merge still lands each record on the right page instead of, say,
        a page boundary falling inside one source's bounded fetch and
        silently dropping records from the other.
        """
        pet_id = str(test_pet["_id"])
        med = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Vitamin C", "username": "testuser"})
        now = datetime.now(timezone.utc)

        # Newest to oldest, alternating event/medication every minute:
        # event(0), intake(1), event(2), intake(3), event(4), intake(5).
        for i in range(6):
            minutes_ago = i
            if i % 2 == 0:
                mock_db["events"].insert_one({
                    "pet_id": pet_id, "type": "asthma",
                    "date_time": now - timedelta(minutes=minutes_ago),
                    "fields": {}, "comment": "", "username": "testuser",
                })
            else:
                mock_db["medication_intakes"].insert_one({
                    "pet_id": pet_id, "medication_id": str(med.inserted_id),
                    "date_time": now - timedelta(minutes=minutes_ago),
                    "dose_taken": "1", "username": "testuser",
                })

        expected_types = ["asthma", "medications", "asthma", "medications", "asthma", "medications"]
        seen_types = []
        for page in (1, 2, 3):
            response = client.get(
                f"/api/history/timeline?pet_id={pet_id}&page={page}&page_size=2",
                headers={"Authorization": f"Bearer {regular_user_token}"}
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["total"] == 6
            assert len(data["items"]) == 2
            seen_types.extend(item["record_type"] for item in data["items"])

        assert seen_types == expected_types

    def test_get_timeline_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """Test that user cannot see timeline for other's pet."""
        pet_id = str(admin_pet["_id"])

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 403

    def test_get_timeline_invalid_pet_id(self, client, regular_user_token):
        """Test timeline with invalid pet_id format."""
        response = client.get(
            "/api/history/timeline?pet_id=invalid_id",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 422
