"""The published reference: open to anyone, valid, and saying how to sign in."""


def test_the_docs_and_spec_need_no_login(client):
    page = client.get("/api/docs")
    assert page.status_code == 200 and b"/api/openapi.json" in page.data
    # The page's own CSP lets ReDoc load; the API's sandbox would blank it.
    assert "cdn.jsdelivr.net" in page.headers["Content-Security-Policy"]
    assert client.get("/api/openapi.json").status_code == 200


def test_the_spec_says_where_and_how(client):
    spec = client.get("/api/openapi.json").get_json()
    assert spec["servers"][0]["url"] == "https://petzy.duckdns.org"
    assert set(spec["components"]["securitySchemes"]) == {"bearerAuth", "cookieAuth"}
    assert spec["paths"]["/api/auth/login"]["post"]["security"] == []
    assert "security" not in spec["paths"]["/api/pets"]["get"]  # the global one applies
    assert "multipart/form-data" in spec["paths"]["/api/documents"]["post"]["requestBody"]["content"]


def test_every_item_schema_has_its_id(client):
    schemas = client.get("/api/openapi.json").get_json()["components"]["schemas"]
    for name in ("PetResponse", "EventItem", "MedicationItem", "MedicationIntakeItem", "DocumentItem", "UserResponse"):
        assert "_id" in schemas[name]["properties"], name


def test_the_dev_outbox_is_not_published(client):
    assert "/api/dev/outbox" not in client.get("/api/openapi.json").get_json()["paths"]
