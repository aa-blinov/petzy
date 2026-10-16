"""Which routes a personal access token reaches, and with which scope, as the app itself registers them.

The list lives in the decorators (``pat_allowed``). This file reads the marks back from the app, so a route that gains
or loses one changes what tokens can do, and that change has to be made here on purpose.
"""

import pytest

from web.app import app
from web.decorators import pat_allowed
from web.security import PAT_SCOPE_ATTR, PERSONAL_TOKEN_SCOPES

OPEN_TO_TOKENS = {
    "pets.get_pets": "pets:read",
    "pets.get_pet": "pets:read",
    "events.list_event_types": "pets:read",
    "events.create_event": "events:write",
    "events.get_history_timeline": "history:read",
    "medical_card.get_medical_card": "medical:read",
}

# The public endpoints of the token management: signed in with the login only, so none of them is marked.
MANAGEMENT = {
    "personal_tokens.create_personal_token": ("post", "/api/me/tokens"),
    "personal_tokens.list_personal_tokens": ("get", "/api/me/tokens"),
    "personal_tokens.revoke_personal_token": ("delete", "/api/me/tokens/{token_id}"),
}


def _marked():
    return {
        endpoint: getattr(view, PAT_SCOPE_ATTR)
        for endpoint, view in app.view_functions.items()
        if getattr(view, PAT_SCOPE_ATTR, None)
    }


def test_exactly_the_six_routes_are_open_to_a_token():
    assert _marked() == OPEN_TO_TOKENS


def test_each_scope_is_asked_for_by_some_route():
    assert set(OPEN_TO_TOKENS.values()) == set(PERSONAL_TOKEN_SCOPES)


@pytest.mark.parametrize("endpoint", sorted(MANAGEMENT))
def test_the_token_management_is_not_open_to_a_token(endpoint):
    assert endpoint in app.view_functions
    assert endpoint not in _marked()


def test_a_scope_that_does_not_exist_cannot_be_marked():
    with pytest.raises(ValueError):
        pat_allowed("pets:write")


def test_the_spec_names_the_scope_of_each_open_route(client):
    spec = client.get("/api/openapi.json").get_json()
    expected = {("get", "/api/pets"): "pets:read", ("get", "/api/pets/{pet_id}"): "pets:read"}
    expected |= {
        ("get", "/api/event-types"): "pets:read",
        ("post", "/api/events"): "events:write",
        ("get", "/api/history/timeline"): "history:read",
        ("get", "/api/pets/{pet_id}/medical-card"): "medical:read",
    }
    for (method, path), scope in expected.items():
        operation = spec["paths"][path][method]
        assert f"`{scope}`" in operation["description"], path
        assert operation["responses"]["429"]["description"].startswith("Ограничение: "), path


def test_the_spec_describes_the_token_management_and_the_bearer_form(client):
    spec = client.get("/api/openapi.json").get_json()
    for endpoint, (method, path) in MANAGEMENT.items():
        operation = spec["paths"][path][method]
        assert operation["tags"] == ["tokens"], endpoint
        assert operation["responses"]["401"]["description"], endpoint
    assert "ptz_" in spec["components"]["securitySchemes"]["bearerAuth"]["description"]
