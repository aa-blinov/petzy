"""The published API document as OpenAPI 3.0.3, the form code generators read.

pydantic writes an optional field as ``anyOf: [<type>, {"type": "null"}]``, and writes some bounds as ``ge``/``le``.
Both are OpenAPI 3.1 (JSON Schema 2020-12). swift-openapi-generator 1.x does not read a ``null`` type: it skips the null
branch, and with it the property or the query parameter that branch sits on. Nothing fails. A refresh token goes missing
from the generated request and response, and the sync cursor from the sync query. In 3.0 the same field is
``nullable: true``, and each construct a generator reads is one that 3.0 defines.
"""

NULL = {"type": "null"}
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
# pydantic's names for a bound it could not translate, and their 3.0 form: the limit, and the flag for "exclusive".
BOUNDS = {
    "ge": ("minimum", None),
    "le": ("maximum", None),
    "gt": ("minimum", "exclusiveMinimum"),
    "lt": ("maximum", "exclusiveMaximum"),
}


def to_openapi_30(spec: dict) -> dict:
    """The same document in OpenAPI 3.0.3. A new dict: the one given is not changed."""
    converted = _convert(spec)
    converted["openapi"] = "3.0.3"
    for item in converted.get("paths", {}).values():
        for method, operation in item.items():
            if method in HTTP_METHODS and "requestBody" in operation:
                body = operation["requestBody"]
                if "multipart/form-data" in body.get("content", {}):
                    body["required"] = True  # a generator skips a multipart body that is not required
    return converted


def _convert(node):
    if isinstance(node, list):
        return [_convert(item) for item in node]
    if not isinstance(node, dict):
        return node
    node = {key: _convert(value) for key, value in node.items()}
    if "anyOf" in node and NULL in node["anyOf"]:
        node = _nullable(node)
    for key, (limit, exclusive) in BOUNDS.items():
        if key in node:
            node[limit] = node.pop(key)
            if exclusive:
                node[exclusive] = True
    for bound, limit in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
        if bound in node and not isinstance(node[bound], bool):
            node[limit] = node.pop(bound)
            node[bound] = True
    if node.get("required") == []:
        del node["required"]  # 3.0 wants at least one name; 3.1 allows an empty list
    return node


def _nullable(node: dict) -> dict:
    """An ``anyOf`` with a null branch, as 3.0 has it: the other branch, marked nullable."""
    rest = [option for option in node["anyOf"] if option != NULL]
    siblings = {key: value for key, value in node.items() if key != "anyOf"}
    if len(rest) == 1 and "$ref" not in rest[0] and not set(rest[0]) & set(siblings):
        return {**rest[0], **siblings, "nullable": True}
    if len(rest) == 1:
        # A $ref ignores its siblings in 3.0, and so does a branch whose keys clash with them: wrap the branch.
        return {"allOf": rest, **siblings, "nullable": True}
    return {"anyOf": rest, **siblings, "nullable": True}
