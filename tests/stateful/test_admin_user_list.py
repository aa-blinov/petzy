"""The admin account list: a page at a time, and a search by login or name.

The search runs over every account whatever is typed into it, so it stays
behind @admin_required and nowhere else — the signed-in account lookup
(GET /api/users/search) is the narrow one and must not grow into this.
"""

import pytest
from datetime import datetime, timedelta, timezone

from tests.conftest import password_hash_for


def _add_user(db, username, full_name, created_at):
    db["users"].insert_one(
        {
            "username": username,
            "password_hash": password_hash_for(b"test123"),
            "full_name": full_name,
            "email": f"{username}@example.com",
            "created_at": created_at,
            "created_by": "admin",
            "is_active": True,
        }
    )


@pytest.fixture
def many_users(mock_db):
    """Thirty accounts with known names, oldest last."""
    from web.app import db

    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(30):
        _add_user(db, f"user{i:02d}", f"Имя Фамилия {i:02d}", base + timedelta(days=i))
    return db["users"]


@pytest.mark.admin
class TestAdminUserListPaging:
    def test_list_is_a_page_and_says_how_many_there_are(self, client, many_users, auth_headers):
        response = client.get("/api/users", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] >= 31  # 30 plus the fixtures' own accounts
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert len(data["users"]) == 20

    def test_second_page_does_not_repeat_the_first(self, client, many_users, auth_headers):
        first = client.get("/api/users", headers=auth_headers).get_json()
        second = client.get("/api/users?page=2", headers=auth_headers).get_json()

        assert second["page"] == 2
        first_ids = {u["username"] for u in first["users"]}
        second_ids = {u["username"] for u in second["users"]}
        assert first_ids.isdisjoint(second_ids)

    def test_a_bad_page_number_reads_as_the_first(self, client, many_users, auth_headers):
        for raw in ("abc", "0", "-3"):
            data = client.get(f"/api/users?page={raw}", headers=auth_headers).get_json()
            assert data["page"] == 1


@pytest.mark.admin
class TestAdminUserSearch:
    def test_search_by_login(self, client, many_users, auth_headers):
        data = client.get("/api/users?q=user07", headers=auth_headers).get_json()

        assert data["total"] == 1
        assert data["users"][0]["username"] == "user07"

    def test_search_by_name(self, client, many_users, auth_headers):
        data = client.get("/api/users?q=Фамилия 12", headers=auth_headers).get_json()

        assert data["total"] == 1
        assert data["users"][0]["username"] == "user12"

    def test_search_ignores_case_and_special_characters(self, client, many_users, auth_headers):
        assert client.get("/api/users?q=USER08", headers=auth_headers).get_json()["total"] == 1
        # A regex typed as text stays text and matches nothing.
        assert client.get("/api/users?q=user.*", headers=auth_headers).get_json()["total"] == 0

    def test_search_that_finds_nothing_is_an_empty_page_not_an_error(self, client, many_users, auth_headers):
        response = client.get("/api/users?q=nosuchperson", headers=auth_headers)

        assert response.status_code == 200
        assert response.get_json() == {"users": [], "total": 0, "page": 1, "per_page": 20}

    def test_search_is_paged_too(self, client, many_users, auth_headers):
        data = client.get("/api/users?q=Фамилия&page=2", headers=auth_headers).get_json()

        assert data["page"] == 2
        assert data["total"] == 30
        assert len(data["users"]) == 10


@pytest.mark.admin
class TestSearchStaysAdminOnly:
    def test_a_signed_in_person_cannot_search_every_account(self, client, many_users, regular_user_token):
        """The leak this decision is about: any account's logins, readable by anyone signed in."""
        for query in ("", "user07", "Фамилия 12", "user.*"):
            response = client.get(f"/api/users?q={query}", headers={"Authorization": f"Bearer {regular_user_token}"})
            assert response.status_code == 403, query
            assert "users" not in response.get_json()

    def test_the_public_account_lookup_is_not_given_the_same_reach(self, client, many_users, regular_user_token):
        """GET /api/users/search stays what it is: the caller's own circle and a whole login typed in full."""
        # A whole login typed in full is found — that is how you share with someone.
        whole_login = client.get(
            "/api/users/search?q=user07", headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert whole_login.get_json()["users"] == [{"username": "user07"}]

        # A part of one is not, and neither is anything shorter than two characters:
        # no walking along somebody else's login one character at a time.
        for query in ("user0", "user07user08", "Фамилия 12"):
            response = client.get(
                f"/api/users/search?q={query}", headers={"Authorization": f"Bearer {regular_user_token}"}
            )
            assert response.get_json()["users"] == [], query

        # And the admin search stays on the admin side only.
        assert (
            client.get("/api/users?q=user07", headers={"Authorization": f"Bearer {regular_user_token}"}).status_code
            == 403
        )

    def test_an_anonymous_caller_gets_nothing(self, client, many_users):
        assert client.get("/api/users?q=user07").status_code == 401
