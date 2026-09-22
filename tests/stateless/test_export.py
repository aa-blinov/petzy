"""Tests for data export endpoints.

Export specs are now built from the ``event_types`` registry at request
time (see ``web/export.py::_build_export_specs``), so these tests exercise
that dynamic path against the ``events`` collection instead of one
hand-rolled collection per type.
"""

import csv
import io
import zipfile
from datetime import datetime

import pytest


def _insert_event(db, pet_id, event_type, when, fields=None, comment="Test", username="testuser"):
    doc = {
        "pet_id": pet_id,
        "type": event_type,
        "date_time": when,
        "fields": fields or {},
        "comment": comment,
        "username": username,
    }
    db["events"].insert_one(doc)
    return doc


@pytest.mark.health
class TestDataExport:
    """Test data export endpoints."""

    @pytest.mark.parametrize(
        "event_type,fields,expected_header",
        [
            ("asthma", {"duration": "5 минут", "reason": "Стресс", "inhalation": "true"}, "Ингаляция"),
            ("defecation", {"stool_type": "Обычный", "color": "Коричневый"}, "Тип стула"),
            ("litter", {}, "Комментарий"),
            ("weight", {"weight": 4.5}, "Вес (кг)"),
            ("feeding", {"food_weight": 100}, "Вес корма"),
            ("eye_drops", {"drops_type": "Обычные"}, "Тип капель"),
            ("tooth_brushing", {"brushing_type": "Щетка"}, "Способ чистки"),
            ("ear_cleaning", {"cleaning_type": "Капли"}, "Способ чистки"),
        ],
    )
    def test_export_builtin_type_csv(
        self, client, mock_db, regular_user_token, test_pet, event_type, fields, expected_header
    ):
        """Every builtin event type exports as CSV with its own field columns."""
        _insert_event(mock_db, str(test_pet["_id"]), event_type, datetime(2024, 1, 15, 14, 30), fields)

        response = client.get(
            f"/api/export/{event_type}/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/csv"
        content = response.data.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 2  # header + 1 row
        assert "Дата и время" in rows[0]
        assert "Пользователь" in rows[0]
        assert expected_header in rows[0]

    @pytest.mark.parametrize(
        "format_type,content_type",
        [
            ("tsv", "text/tab-separated-values"),
            ("html", "text/html"),
            ("md", "text/markdown"),
        ],
    )
    def test_export_other_formats(self, client, mock_db, regular_user_token, test_pet, format_type, content_type):
        """The other three formats also work for an events-backed type."""
        _insert_event(
            mock_db,
            str(test_pet["_id"]),
            "defecation",
            datetime(2024, 1, 15, 14, 30),
            {"stool_type": "Обычный", "color": "Коричневый"},
        )

        response = client.get(
            f"/api/export/defecation/{format_type}?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == content_type
        content = response.data.decode("utf-8")
        assert "Пользователь" in content
        assert "Дефекация" in content or format_type == "tsv"  # tsv has no title line

    def test_export_medications_csv(self, client, mock_db, regular_user_token, test_pet):
        """Medications keep their own static export spec, unaffected by the registry."""
        med = mock_db["medications"].insert_one(
            {"pet_id": str(test_pet["_id"]), "name": "Vitamin C", "username": "testuser"}
        )
        mock_db["medication_intakes"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "medication_id": str(med.inserted_id),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "dose_taken": "1 таблетка",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/medications/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8-sig")
        assert "Vitamin C" in content

    def test_export_all_types_zip(self, client, mock_db, regular_user_token, test_pet):
        """'all' bundles every type that has records into one ZIP, medications included."""
        pet_id = str(test_pet["_id"])
        _insert_event(mock_db, pet_id, "weight", datetime(2024, 1, 15, 14, 30), {"weight": 4.5})
        _insert_event(mock_db, pet_id, "feeding", datetime(2024, 1, 15, 8, 0), {"food_weight": 100})
        med = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Vitamin C", "username": "testuser"})
        mock_db["medication_intakes"].insert_one(
            {
                "pet_id": pet_id,
                "medication_id": str(med.inserted_id),
                "date_time": datetime(2024, 1, 15, 9, 0),
                "dose_taken": "1",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/all/csv?pet_id={pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "application/zip"
        archive = zipfile.ZipFile(io.BytesIO(response.data))
        names = archive.namelist()
        # Only types with data are included — asthma etc. have none.
        assert any("вес" in n for n in names)
        assert any("порц" in n for n in names)
        assert any("препарат" in n for n in names)
        assert not any("астма" in n for n in names)

    def test_export_custom_type(self, client, mock_db, regular_user_token, test_pet):
        """A user-created event type is exportable immediately — no code change needed."""
        create = client.post(
            "/api/event-types",
            json={
                "label": "Игра",
                "icon": "paw",
                "color": "blue",
                "fields": [{"name": "duration_min", "label": "Длительность (мин)", "type": "number", "required": True}],
                "chart": {"kind": "count"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        key = create.get_json()["key"]
        _insert_event(mock_db, str(test_pet["_id"]), key, datetime(2024, 1, 15, 14, 30), {"duration_min": 15})

        response = client.get(
            f"/api/export/{key}/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8-sig")
        assert "Длительность (мин)" in content
        assert "15.0" in content or "15" in content

    def test_export_requires_pet_id(self, client, regular_user_token):
        """Test that export requires pet_id."""
        response = client.get("/api/export/asthma/csv", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_export_invalid_type(self, client, regular_user_token, test_pet):
        """Test export with invalid export type."""
        response = client.get(
            f"/api/export/invalid/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_export_invalid_format(self, client, mock_db, regular_user_token, test_pet):
        """Test export with invalid format type."""
        _insert_event(mock_db, str(test_pet["_id"]), "asthma", datetime(2024, 1, 15, 14, 30))

        response = client.get(
            f"/api/export/asthma/invalid?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_export_no_data(self, client, mock_db, regular_user_token, test_pet):
        """Test export when no data exists."""
        response = client.get(
            f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_export_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """Test export without pet access."""
        response = client.get(
            f"/api/export/asthma/csv?pet_id={admin_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_export_csv_encoding(self, client, mock_db, regular_user_token, test_pet):
        """Test CSV export has proper encoding (UTF-8 with BOM for Excel)."""
        _insert_event(
            mock_db,
            str(test_pet["_id"]),
            "asthma",
            datetime(2024, 1, 15, 14, 30),
            {"duration": "5 минут", "reason": "Стресс"},
            comment="Тест",
        )

        response = client.get(
            f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.data.startswith(b"\xef\xbb\xbf") or response.data.startswith(b"\xff\xfe")

    def test_export_handles_empty_values(self, client, mock_db, regular_user_token, test_pet):
        """Test export handles empty comments correctly."""
        _insert_event(
            mock_db,
            str(test_pet["_id"]),
            "asthma",
            datetime(2024, 1, 15, 14, 30),
            {"duration": "5 minutes", "reason": "Stress"},
            comment="",
        )

        response = client.get(
            f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8-sig")
        assert "-" in content

    def test_export_handles_missing_username(self, client, mock_db, regular_user_token, test_pet):
        """Test export handles records without username (old records)."""
        mock_db["events"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "type": "asthma",
                "date_time": datetime(2024, 1, 15, 14, 30),
                "fields": {"duration": "5 minutes", "reason": "Stress"},
                "comment": "Test",
                # No username field
            }
        )

        response = client.get(
            f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8-sig")
        assert "-" in content

    def test_export_humanizes_select_values(self, client, mock_db, regular_user_token, test_pet):
        """A select field's stored value (e.g. inhalation='true') is shown by
        its display text ('Да'), not the raw stored value."""
        _insert_event(
            mock_db,
            str(test_pet["_id"]),
            "asthma",
            datetime(2024, 1, 15, 14, 30),
            {"duration": "5 minutes", "reason": "Stress", "inhalation": "true"},
        )

        response = client.get(
            f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8-sig")
        assert "Да" in content
        assert "true" not in content

    def test_export_handles_special_characters(self, client, mock_db, regular_user_token, test_pet):
        """Test export handles special characters in data."""
        _insert_event(
            mock_db,
            str(test_pet["_id"]),
            "defecation",
            datetime(2024, 1, 15, 14, 30),
            {"stool_type": "Normal", "food": "Food with | pipe & < > symbols"},
            comment="Comment with <script>alert('xss')</script>",
        )

        response = client.get(
            f"/api/export/defecation/html?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8")
        assert "&lt;" in content or "&gt;" in content
        assert "<script>" not in content

    def test_export_markdown_escapes_pipes(self, client, mock_db, regular_user_token, test_pet):
        """Test Markdown export escapes pipe characters."""
        _insert_event(
            mock_db,
            str(test_pet["_id"]),
            "weight",
            datetime(2024, 1, 15, 14, 30),
            {"weight": 4.5, "food": "Food | with | pipes"},
        )

        response = client.get(
            f"/api/export/weight/md?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8")
        assert "\\|" in content

    def test_export_all_types_no_data_returns_error(self, client, mock_db, regular_user_token, test_pet):
        response = client.get(
            f"/api/export/all/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_export_unexpected_value_error_handled(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import patch

        with patch("web.export._build_export_specs", side_effect=ValueError("simulated")):
            response = client.get(
                f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 422

    def test_enrich_medication_names_noop_when_no_medication_ids(self):
        """Pure-function edge case: a records list with no
        medication_id at all (or none set) should be a safe no-op, not
        an unnecessary empty $in query."""
        from web.export import _enrich_medication_names

        records = [{"pet_id": "x", "dose_taken": "1"}]
        _enrich_medication_names({}, records)

        assert "medication_name" not in records[0]
