"""The published document is OpenAPI 3.0.3, the form the Swift generator reads without losing fields (web/openapi_30.py)."""

import copy

from openapi_spec_validator import validate

from web.openapi_30 import to_openapi_30

PET_REF = "#/components/schemas/Pet"


def _property(**schema):
    return to_openapi_30({"type": "object", "properties": {"x": schema}})["properties"]["x"]


def test_an_optional_field_is_nullable_and_keeps_its_type():
    assert _property(anyOf=[{"type": "string", "maxLength": 5}, {"type": "null"}], default=None, title="X") == {
        "type": "string",
        "maxLength": 5,
        "default": None,
        "title": "X",
        "nullable": True,
    }


def test_an_optional_reference_is_wrapped_so_the_flag_applies():
    assert _property(anyOf=[{"$ref": PET_REF}, {"type": "null"}], default=None) == {
        "allOf": [{"$ref": PET_REF}],
        "default": None,
        "nullable": True,
    }


def test_pydantic_bounds_become_minimum_and_maximum():
    schemas = to_openapi_30(
        {
            "components": {
                "schemas": {
                    "Closed": {"type": "number", "ge": 0, "le": 60},
                    "Open": {"type": "number", "gt": 0, "lt": 1},
                    "OpenBelow": {"type": "number", "exclusiveMinimum": 0, "maximum": 4000},
                }
            }
        }
    )["components"]["schemas"]

    assert schemas["Closed"] == {"type": "number", "minimum": 0, "maximum": 60}
    assert schemas["Open"] == {
        "type": "number",
        "minimum": 0,
        "exclusiveMinimum": True,
        "maximum": 1,
        "exclusiveMaximum": True,
    }
    assert schemas["OpenBelow"] == {"type": "number", "minimum": 0, "exclusiveMinimum": True, "maximum": 4000}


def test_an_empty_required_list_is_dropped_and_a_multipart_body_is_required():
    spec = {
        "paths": {
            "/api/pets": {
                "post": {
                    "requestBody": {
                        "content": {"multipart/form-data": {"schema": {"type": "object", "required": []}}},
                    }
                }
            }
        }
    }

    body = to_openapi_30(spec)["paths"]["/api/pets"]["post"]["requestBody"]

    assert body["required"] is True
    assert "required" not in body["content"]["multipart/form-data"]["schema"]


def test_the_document_given_is_not_changed():
    spec = {"openapi": "3.1.0", "components": {"schemas": {"A": {"anyOf": [{"type": "string"}, {"type": "null"}]}}}}
    before = copy.deepcopy(spec)

    to_openapi_30(spec)

    assert spec == before


def test_the_served_document_is_openapi_30_and_valid(client):
    spec = client.get("/api/openapi.json").get_json()

    assert spec["openapi"] == "3.0.3"
    validate(spec)


def test_the_served_document_keeps_what_the_generated_client_needs(client):
    spec = client.get("/api/openapi.json").get_json()

    refresh = spec["components"]["schemas"]["AuthRefreshRequest"]["properties"]["refresh_token"]
    sync = [parameter["name"] for parameter in spec["paths"]["/api/sync"]["get"]["parameters"]]

    assert refresh["nullable"] is True
    assert {"since", "after", "page_size"} <= set(sync)


def test_nothing_of_3_1_is_left_in_the_served_document(client):
    spec = client.get("/api/openapi.json").get_json()
    found = []

    def walk(node, where):
        if isinstance(node, dict):
            if node.get("type") == "null" or any(option == {"type": "null"} for option in node.get("anyOf", [])):
                found.append(where)
            for key in ("ge", "le", "gt", "lt"):
                if key in node:
                    found.append(f"{where}/{key}")
            for key in ("exclusiveMinimum", "exclusiveMaximum"):
                if key in node and not isinstance(node[key], bool):
                    found.append(f"{where}/{key}")
            if node.get("required") == []:
                found.append(f"{where}/required")
            for key, value in node.items():
                walk(value, f"{where}/{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{where}[{index}]")

    walk(spec, "#")

    assert found == []
