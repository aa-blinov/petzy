"""«Настройки форм» live on the account, shared by all of a user's devices."""


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestFormDefaults:
    def test_empty_until_saved(self, client, regular_user_token):
        response = client.get("/api/me/form-defaults", headers=_auth(regular_user_token))
        assert response.status_code == 200
        assert response.get_json() == {"form_defaults": {}}

    def test_saved_values_come_back(self, client, regular_user_token):
        body = {
            "form_defaults": {"defecation": {"food": "Hill's", "color": "Коричневый"}, "weight": {"food": "Hill's"}}
        }
        assert client.put("/api/me/form-defaults", json=body, headers=_auth(regular_user_token)).status_code == 200
        response = client.get("/api/me/form-defaults", headers=_auth(regular_user_token))
        assert response.get_json() == body

    def test_each_user_has_their_own(self, client, regular_user_token, auth_headers):
        client.put(
            "/api/me/form-defaults",
            json={"form_defaults": {"weight": {"food": "Hill's"}}},
            headers=_auth(regular_user_token),
        )
        assert client.get("/api/me/form-defaults", headers=auth_headers).get_json() == {"form_defaults": {}}

    def test_nested_objects_and_huge_values_are_refused(self, client, regular_user_token):
        for bad in (
            {"form_defaults": {"weight": {"food": {"nested": "x"}}}},
            {"form_defaults": {"weight": {"food": "x" * 1000}}},
            {"form_defaults": {f"form{i}": {} for i in range(100)}},
        ):
            response = client.put("/api/me/form-defaults", json=bad, headers=_auth(regular_user_token))
            assert response.status_code in (400, 422), bad

    def test_needs_a_login(self, client):
        assert client.get("/api/me/form-defaults").status_code == 401
