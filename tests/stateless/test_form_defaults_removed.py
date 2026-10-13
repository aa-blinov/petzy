"""The account-level form defaults are gone: the app keeps them per pet (PUT /api/pets/{pet_id}/form-defaults)."""


def test_the_account_level_form_defaults_route_is_gone(client, auth_headers):
    assert client.get("/api/me/form-defaults", headers=auth_headers).status_code == 404
    assert client.put("/api/me/form-defaults", json={"form_defaults": {}}, headers=auth_headers).status_code == 404
    assert "/api/me/form-defaults" not in client.get("/api/openapi.json").get_json()["paths"]
