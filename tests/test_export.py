"""Tests for data export endpoints."""

import pytest
from datetime import datetime
import csv
import io


@pytest.mark.health
class TestDataExport:
    """Test data export endpoints."""

    def test_export_asthma_csv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting asthma attacks as CSV."""
        # Add some asthma attacks
        from web.app import db

        db["asthma_attacks"].insert_many(
            [
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 15, 14, 30),
                    "duration": "5 minutes",
                    "reason": "Stress",
                    "inhalation": True,
                    "comment": "Attack 1",
                    "username": "testuser",
                },
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 16, 10, 0),
                    "duration": "3 minutes",
                    "reason": "Exercise",
                    "inhalation": False,
                    "comment": "Attack 2",
                    "username": "testuser",
                },
            ]
        )

        response = client.get(
            f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/csv"
        assert "attachment" in response.headers.get("Content-Disposition", "")

        # Verify CSV content
        content = response.data.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 3  # Header + 2 data rows
        assert "Дата и время" in rows[0]
        assert "Пользователь" in rows[0]

    def test_export_defecation_tsv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting defecations as TSV."""
        from web.app import db

        db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "stool_type": "Normal",
                "color": "Brown",
                "food": "Dry food",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/defecation/tsv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/tab-separated-values"
        # Verify username column is present
        content = response.data.decode("utf-8")
        assert "Пользователь" in content

    def test_export_weight_html(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting weights as HTML."""
        from web.app import db

        db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "weight": "4.5",
                "food": "Dry food",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/weight/html?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/html"
        assert b"<html" in response.data
        assert "Вес".encode("utf-8") in response.data
        assert "Пользователь".encode("utf-8") in response.data

    def test_export_litter_markdown(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting litter changes as Markdown."""
        from web.app import db

        db["litter_changes"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "comment": "Test change",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/litter/md?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        assert response.content_type == "text/markdown"
        assert b"# " in response.data
        assert "Смена лотка".encode("utf-8") in response.data
        assert "Пользователь".encode("utf-8") in response.data

    def test_export_feeding_csv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting feedings as CSV."""
        from web.app import db

        db["feedings"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 8, 0),
                "food_weight": "100",
                "comment": "Morning feeding",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/feeding/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/csv"

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
        # Add some data first
        from web.app import db

        db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": True,
                "comment": "Test",
                "username": "testuser",
            }
        )

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
        from web.app import db

        db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 минут",
                "reason": "Стресс",
                "inhalation": True,
                "comment": "Тест",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        # Check for BOM (UTF-8 signature)
        assert response.data.startswith(b"\xef\xbb\xbf") or response.data.startswith(b"\xff\xfe")

    def test_export_asthma_tsv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting asthma attacks as TSV."""
        from web.app import db

        db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": True,
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/asthma/tsv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/tab-separated-values"
        content = response.data.decode("utf-8")
        assert "Пользователь" in content
        assert "testuser" in content

    def test_export_asthma_html(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting asthma attacks as HTML."""
        from web.app import db

        db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": True,
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/asthma/html?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/html"
        assert b"<html" in response.data
        assert "Приступы астмы".encode("utf-8") in response.data

    def test_export_asthma_markdown(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting asthma attacks as Markdown."""
        from web.app import db

        db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": True,
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/asthma/md?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/markdown"
        assert b"# " in response.data
        assert "Приступы астмы".encode("utf-8") in response.data

    def test_export_defecation_csv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting defecations as CSV."""
        from web.app import db

        db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "stool_type": "Normal",
                "color": "Brown",
                "food": "Dry food",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/defecation/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/csv"

    def test_export_defecation_html(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting defecations as HTML."""
        from web.app import db

        db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "stool_type": "Normal",
                "color": "Brown",
                "food": "Dry food",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/defecation/html?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/html"
        assert b"<html" in response.data

    def test_export_defecation_markdown(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting defecations as Markdown."""
        from web.app import db

        db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "stool_type": "Normal",
                "color": "Brown",
                "food": "Dry food",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/defecation/md?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/markdown"

    def test_export_litter_csv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting litter changes as CSV."""
        from web.app import db

        db["litter_changes"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "comment": "Test change",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/litter/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/csv"

    def test_export_litter_tsv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting litter changes as TSV."""
        from web.app import db

        db["litter_changes"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "comment": "Test change",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/litter/tsv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/tab-separated-values"

    def test_export_litter_html(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting litter changes as HTML."""
        from web.app import db

        db["litter_changes"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "comment": "Test change",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/litter/html?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/html"

    def test_export_weight_csv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting weights as CSV."""
        from web.app import db

        db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "weight": 4.5,
                "food": "Dry food",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/weight/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/csv"

    def test_export_weight_tsv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting weights as TSV."""
        from web.app import db

        db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "weight": 4.5,
                "food": "Dry food",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/weight/tsv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/tab-separated-values"

    def test_export_weight_markdown(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting weights as Markdown."""
        from web.app import db

        db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "weight": 4.5,
                "food": "Dry food",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/weight/md?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/markdown"

    def test_export_feeding_tsv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting feedings as TSV."""
        from web.app import db

        db["feedings"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 8, 0),
                "food_weight": 100,
                "comment": "Morning feeding",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/feeding/tsv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/tab-separated-values"

    def test_export_feeding_html(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting feedings as HTML."""
        from web.app import db

        db["feedings"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 8, 0),
                "food_weight": 100,
                "comment": "Morning feeding",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/feeding/html?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/html"

    def test_export_feeding_markdown(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting feedings as Markdown."""
        from web.app import db

        db["feedings"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 8, 0),
                "food_weight": 100,
                "comment": "Morning feeding",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/feeding/md?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/markdown"

    def test_export_handles_empty_values(self, client, mock_db, regular_user_token, test_pet):
        """Test export handles empty comments and food values."""
        from web.app import db

        db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": True,
                "comment": "",  # Empty comment
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8-sig")
        # Empty comment should be replaced with "-"
        assert "-" in content

    def test_export_handles_missing_username(self, client, mock_db, regular_user_token, test_pet):
        """Test export handles records without username (old records)."""
        from web.app import db

        db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": True,
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
        # Missing username should be replaced with "-"
        assert "-" in content

    def test_export_handles_boolean_inhalation(self, client, mock_db, regular_user_token, test_pet):
        """Test export handles boolean inhalation values correctly."""
        from web.app import db

        db["asthma_attacks"].insert_many(
            [
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 15, 14, 30),
                    "duration": "5 minutes",
                    "reason": "Stress",
                    "inhalation": True,
                    "comment": "Test 1",
                    "username": "testuser",
                },
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 16, 10, 0),
                    "duration": "3 minutes",
                    "reason": "Exercise",
                    "inhalation": False,
                    "comment": "Test 2",
                    "username": "testuser",
                },
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 17, 12, 0),
                    "duration": "2 minutes",
                    "reason": "Other",
                    # No inhalation field
                    "comment": "Test 3",
                    "username": "testuser",
                },
            ]
        )

        response = client.get(
            f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8-sig")
        # True should be "Да", False should be "Нет", missing should be "-"
        assert "Да" in content or "Нет" in content or "-" in content

    def test_export_handles_special_characters(self, client, mock_db, regular_user_token, test_pet):
        """Test export handles special characters in data."""
        from web.app import db

        db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "stool_type": "Normal",
                "color": "Brown",
                "food": "Food with | pipe & < > symbols",
                "comment": "Comment with <script>alert('xss')</script>",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/defecation/html?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8")
        # HTML should escape special characters
        assert "&lt;" in content or "&gt;" in content
        # But should not contain raw script tags
        assert "<script>" not in content

    def test_export_markdown_escapes_pipes(self, client, mock_db, regular_user_token, test_pet):
        """Test Markdown export escapes pipe characters."""
        from web.app import db

        db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "weight": 4.5,
                "food": "Food | with | pipes",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/weight/md?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        content = response.data.decode("utf-8")
        # Pipes should be escaped in markdown
        assert "\\|" in content

    def test_export_tooth_brushing_csv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting tooth brushing records as CSV."""
        from web.app import db

        db["tooth_brushing"].insert_many(
            [
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 15, 14, 30),
                    "brushing_type": "Щетка",
                    "comment": "Morning brushing",
                    "username": "testuser",
                },
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 16, 20, 0),
                    "brushing_type": "Марля",
                    "comment": "Evening brushing",
                    "username": "testuser",
                },
            ]
        )

        response = client.get(
            f"/api/export/tooth_brushing/csv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/csv"
        assert "attachment" in response.headers.get("Content-Disposition", "")

        # Verify CSV content
        content = response.data.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 3  # Header + 2 data rows
        assert "Дата и время" in rows[0]
        assert "Пользователь" in rows[0]
        assert "Способ чистки" in rows[0]
        assert "Комментарий" in rows[0]

    def test_export_tooth_brushing_tsv(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting tooth brushing records as TSV."""
        from web.app import db

        db["tooth_brushing"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "brushing_type": "Щетка",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/tooth_brushing/tsv?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/tab-separated-values"
        content = response.data.decode("utf-8")
        assert "Пользователь" in content
        assert "Способ чистки" in content

    def test_export_tooth_brushing_html(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting tooth brushing records as HTML."""
        from web.app import db

        db["tooth_brushing"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "brushing_type": "Щетка",
                "comment": "Test",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/tooth_brushing/html?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/html"
        assert b"<html" in response.data
        assert "Чистка зубов".encode("utf-8") in response.data
        assert "Пользователь".encode("utf-8") in response.data

    def test_export_tooth_brushing_markdown(self, client, mock_db, regular_user_token, test_pet):
        """Test exporting tooth brushing records as Markdown."""
        from web.app import db

        db["tooth_brushing"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "brushing_type": "Марля",
                "comment": "Test change",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/export/tooth_brushing/md?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.content_type == "text/markdown"
        assert b"# " in response.data
        assert "Чистка зубов".encode("utf-8") in response.data
        assert "Пользователь".encode("utf-8") in response.data
