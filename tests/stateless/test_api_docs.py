"""The published reference: open to anyone, valid, and saying how to sign in."""

import json


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


def _operations(spec):
    return [
        (path, method, operation)
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in ("get", "post", "put", "patch", "delete")
    ]


def test_every_route_outside_public_says_401(client):
    """A client has no other way to learn which calls need a token.

    It used to be eight operations out of a hundred, and three of the others were
    the reverse mistake: a vet's shared card and the reset check need no account
    at all, while the spec asked for a bearer token.
    """
    spec = client.get("/api/openapi.json").get_json()
    missing = [
        f"{m.upper()} {p}"
        for p, m, o in _operations(spec)
        if "401" not in o.get("responses", {}) and o.get("security") != []
    ]
    public = [f"{m.upper()} {p}" for p, m, o in _operations(spec) if o.get("security") == []]
    assert public, "nothing is public any more, which cannot be right"
    assert not missing, missing


def test_public_routes_are_really_public(client):
    """The link a vet opens with no account, and the page behind the reset letter."""
    spec = client.get("/api/openapi.json").get_json()
    for path, method in (("/api/shared/medical-card/{token}", "get"), ("/api/auth/password/reset/check", "get")):
        assert spec["paths"][path][method].get("security") == [], f"{method.upper()} {path}"


def test_a_limited_route_says_429_with_the_limit(client):
    spec = client.get("/api/openapi.json").get_json()
    for path, method in (("/api/auth/login", "post"), ("/api/auth/register", "post"), ("/api/images/preview", "post")):
        rate_limited = spec["paths"][path][method]["responses"]["429"]
        assert rate_limited["description"].startswith("Ограничение: "), rate_limited


def test_every_operation_explains_itself(client):
    """A one-line summary tells a reader the call exists, not what it does.

    Only 36 of the 101 operations said anything more than their summary: what
    the call changes, who may make it, what it refuses. The rest is what an
    integrator reads before deciding how to use the API.
    """
    spec = client.get("/api/openapi.json").get_json()
    thin = [f"{m.upper()} {p}" for p, m, o in _operations(spec) if len(o.get("description", "")) < 40]
    assert not thin, thin


def test_a_description_is_a_sentence_and_not_a_scrap(client):
    """A docstring whose first sentence wraps onto the next line loses its subject.

    The first source line becomes the summary and the rest becomes the
    description, so the published text opened with «one continues with fresh
    cookies.» and three more like it. A description starts with a capital.
    """
    spec = client.get("/api/openapi.json").get_json()
    scraps = [
        f"{m.upper()} {p}: {o['description'][:60]}"
        for p, m, o in _operations(spec)
        if o.get("description") and o["description"][:1].islower()
    ]
    assert not scraps, scraps


def test_a_schema_a_client_reads_has_an_example(client):
    """Types on their own are not enough to build a client from.

    37 of 139 schemas carried an example. The rest were a list of names and
    types, and the values that show what those types really hold had to be
    guessed from the demo data.
    """
    spec = client.get("/api/openapi.json").get_json()
    schemas = spec["components"]["schemas"]
    read_by_a_client = set()

    def collect(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                read_by_a_client.add(ref.rsplit("/", 1)[1])
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    for item in spec["paths"].values():
        for operation in item.values():
            collect(operation.get("responses", {}))
            collect(operation.get("requestBody", {}))

    bare = sorted(n for n in read_by_a_client if "example" not in json.dumps(schemas.get(n, {})))
    assert not bare, bare


def test_every_operation_can_be_named_and_grouped(client):
    """operationId is what a generator calls the method, so it has to be there and unique."""
    spec = client.get("/api/openapi.json").get_json()
    declared = {tag["name"] for tag in spec["tags"]}
    ids, problems = [], []
    for path, method, operation in _operations(spec):
        if not operation.get("summary"):
            problems.append(f"нет summary: {method.upper()} {path}")
        if not operation.get("operationId"):
            problems.append(f"нет operationId: {method.upper()} {path}")
        else:
            ids.append(operation["operationId"])
        for tag in operation.get("tags", []):
            if tag not in declared:
                problems.append(f"группа {tag} не объявлена: {method.upper()} {path}")
    assert not problems, problems
    assert len(ids) == len(set(ids)), "operationId повторяется"


# Actions that read nothing from the request: the path and the session say it all.
BODYLESS = {
    ("post", "/api/documents/uploads/{upload_id}/cancel"),
    ("post", "/api/me/email/resend"),
    ("post", "/api/pets/{pet_id}/invite/accept"),
    ("post", "/api/pets/{pet_id}/invite/decline"),
    ("post", "/api/pets/{pet_id}/leave"),
}


def test_every_operation_says_what_it_answers_with(client):
    """A call with no success answer in the spec leaves a client to guess its shape.

    used-types and deletion-impact answered JSON that the reference never showed, and
    the two PDFs had a 200 with no type.
    """
    spec = client.get("/api/openapi.json").get_json()
    silent = []
    for path, method, operation in _operations(spec):
        ok = {code: r for code, r in operation.get("responses", {}).items() if code[0] in "23"}
        if not any(code in ("204", "302") or r.get("content") for code, r in ok.items()):
            silent.append(f"{method.upper()} {path}")
    assert not silent, silent


def test_a_call_that_reads_a_body_documents_it(client):
    """Sign-out takes the native app's refresh token in its body, and replacing a document's
    file takes the file: neither was in the reference."""
    spec = client.get("/api/openapi.json").get_json()
    undocumented = [
        f"{method.upper()} {path}"
        for path, method, operation in _operations(spec)
        if method in ("post", "put", "patch") and (method, path) not in BODYLESS and "requestBody" not in operation
    ]
    assert not undocumented, undocumented


def test_every_error_says_what_it_means_here(client):
    """«Not Found» or «Forbidden» says nothing a client can act on: a member gets 404 for a pet it
    cannot see, 403 means owner-only or admin-only, and the code to branch on is named."""
    spec = client.get("/api/openapi.json").get_json()
    generic = {
        "Not Found",
        "Forbidden",
        "Validation Error",
        "Unprocessable Entity",
        "Internal Server Error",
        "Service Unavailable",
        "Unauthorized",
        "Conflict",
    }
    bare = [
        f"{method.upper()} {path} {code}"
        for path, method, operation in _operations(spec)
        for code, response in operation.get("responses", {}).items()
        if response.get("description") in generic
    ]
    assert not bare, bare


def test_each_create_a_retry_may_send_again_takes_the_idempotency_key(client):
    spec = client.get("/api/openapi.json").get_json()
    assert "Idempotency-Key" in spec["info"]["description"]
    for path in (
        "/api/pets",
        "/api/documents",
        "/api/medical-records",
        "/api/medications",
        "/api/medications/{id}/log",
        "/api/events",
        "/api/event-types",
    ):
        names = [parameter["name"] for parameter in spec["paths"][path]["post"].get("parameters", [])]
        assert "Idempotency-Key" in names, path
