"""Backend CRUD audit.

Walks every Flask route in web/ and produces a per-entity report:

  - CRUD coverage (Create/Read-list/Read-one/Update/Delete)
  - HTTP method consistency (PUT vs PATCH)
  - Auth coverage (@require_pet_access / @require_record_access / @admin_required / @login_required)
  - Rate limiting coverage
  - Response shape consistency (jsonify / get_message / error_response)
  - OpenAPI spec coverage (@api.validate)

Output: prints a human-readable summary and writes
audit/backend_crud_audit.json for machine consumption.

Usage:  python3 scripts/audit_backend.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WEB_DIR = Path(__file__).parent.parent / "web"
OUTPUT_PATH = Path(__file__).parent.parent / "audit" / "backend_crud_audit.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Map an entity (noun) to the CRUD operations it should expose, based on
# the route prefixes we know exist in the app.
ENTITIES = {
    "auth":      {"path": "/api/auth"},
    "pets":      {"path": "/api/pets"},
    "users":     {"path": "/api/users"},
    "medications": {"path": "/api/medications  (incl. intakes + /log)"},
    "export":    {"path": "/api/export"},
    "stats":     {"path": "/api/stats"},
    "timeline":  {"path": "/api/history"},
    "health_records": {"path": "/api/{asthma,defecation,litter,weight,feeding,eye_drops,tooth_brushing,ear_cleaning}"},
}


@dataclass
class Route:
    file: str
    line: int
    entity: str
    path: str
    methods: list[str] = field(default_factory=list)
    auth: list[str] = field(default_factory=list)
    rate_limited: bool = False
    validated: bool = False
    response_kind: str = "?"  # jsonify / get_message / error_response / redirect
    crud_op: str = "?"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "path": self.path,
            "methods": self.methods,
            "auth": self.auth,
            "rate_limited": self.rate_limited,
            "validated": self.validated,
            "response": self.response_kind,
            "crud_op": self.crud_op,
        }


# Decorators we treat as auth gates.
AUTH_DECORATORS = {
    "require_pet_access": "pet_access",
    "require_record_access": "record_access",
    "admin_required": "admin",
    "login_required": "login",
    "current_user": "current_user",
}


def classify_crud(methods: list[str], path: str) -> str:
    """Best-effort CRUD classification for a route.

    We treat POST-with-id (e.g. ``/api/medications/<id>/log``) as
    CREATE for the *nested* entity (an intake), not UPDATE for the
    parent — that's how REST treats sub-resource creation.
    """
    m = {x.upper() for x in methods}
    has_id = bool(re.search(r"<[^>]+>", path))
    if "POST" in m:
        return "CREATE"
    if "GET" in m and has_id:
        return "READ_ONE"
    if "GET" in m and not has_id:
        return "READ_LIST"
    if "PUT" in m or "PATCH" in m:
        return "UPDATE"
    if "DELETE" in m:
        return "DELETE"
    return "?"


def parse_routes() -> list[Route]:
    """Walk every web/*.py file and extract Flask routes."""
    routes: list[Route] = []

    # Regex captures: full route-decorator line, the methods, and the path.
    route_pat = re.compile(
        r"""(?P<path>@\w+\.route\(\s*['"](?P<url>[^'"]+)['"]\s*(?:,\s*methods\s*=\s*\[(?P<methods>[^\]]+)\])?\s*\)|@app\.route\(\s*['"](?P<url2>[^'"]+)['"]\s*(?:,\s*methods\s*=\s*\[(?P<methods2>[^\]]+)\])?\s*\))""",
    )

    for path in sorted(WEB_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        text = path.read_text()
        for m in route_pat.finditer(text):
            url = m.group("url") or m.group("url2")
            methods_raw = m.group("methods") or m.group("methods2") or "GET"
            methods = [x.strip().strip("'\"") for x in methods_raw.split(",")]
            if not methods:
                methods = ["GET"]
            line_no = text[:m.start()].count("\n") + 1

            # Pull decorators from BOTH directions: many handlers stack
            # `@bp.route(...)` first and then `@login_required`,
            # `@api.validate(...)`, `@require_pet_access` below it. We
            # walk through multi-line decorator bodies by tracking paren
            # depth, since decorators like `@api.validate(\n  body=...,\n)`
            # span several physical lines.
            block_start = m.start()
            # Walk back through consecutive `@...` decorator lines,
            # including their multi-line bodies.
            cursor = m.start()
            paren_depth = 0
            while True:
                # Step back to the previous newline.
                prev_nl = text.rfind("\n", 0, cursor - 1)
                if prev_nl == -1:
                    break
                line_start = prev_nl + 1
                line = text[line_start: cursor]
                stripped = line.strip()
                if stripped.startswith("@"):
                    # Update paren depth walking backwards.
                    paren_depth += line.count(")") - line.count("(")
                    if paren_depth <= 0:
                        block_start = line_start
                    cursor = line_start
                    paren_depth = 0
                    continue
                if stripped == "":
                    cursor = line_start
                    continue
                break
            # Walk forward through subsequent decorator lines (including
            # multi-line ones) until we hit `def`.
            block_end = text.find("\n", m.end()) + 1
            cursor = block_end
            paren_depth = 0
            while cursor < len(text):
                next_nl = text.find("\n", cursor)
                if next_nl == -1:
                    break
                line = text[cursor: next_nl]
                stripped = line.strip()
                if stripped.startswith("@") and paren_depth == 0:
                    block_end = next_nl
                    paren_depth += line.count("(") - line.count(")")
                    cursor = next_nl + 1
                    continue
                if paren_depth > 0:
                    block_end = next_nl
                    paren_depth += line.count("(") - line.count(")")
                    cursor = next_nl + 1
                    continue
                if stripped == "":
                    cursor = next_nl + 1
                    continue
                break
            block = text[block_start: block_end]
            auth_used = sorted({name for name in AUTH_DECORATORS if f"@{name}" in block})
            rate_limited = "@limiter.limit" in block
            validated = "@api.validate" in block

            # Response style: peek into the file body around the handler.
            # We look at the next 60 lines for a return that hits jsonify
            # / get_message / error_response / redirect.
            handler_start = text.find("\n", m.end()) + 1
            body = text[handler_start: handler_start + 4000]
            if "return redirect(" in body:
                response_kind = "redirect"
            elif "get_message(" in body:
                response_kind = "get_message"
            elif "error_response(" in body:
                response_kind = "error_response"
            elif "jsonify(" in body:
                response_kind = "jsonify"
            else:
                response_kind = "?"

            crud_op = classify_crud(methods, url)
            routes.append(
                Route(
                    file=path.name,
                    line=line_no,
                    entity=classify_entity(url),
                    path=url,
                    methods=methods,
                    auth=auth_used,
                    rate_limited=rate_limited,
                    validated=validated,
                    response_kind=response_kind,
                    crud_op=crud_op,
                )
            )
    return routes


def classify_entity(url: str) -> str:
    """Bucket a URL into the canonical entity list."""
    if url.startswith("/api/auth"):
        return "auth"
    if url.startswith("/api/pets"):
        return "pets"
    if url.startswith("/api/users"):
        return "users"
    # medication_intakes is treated as part of medications: the
    # `/api/medications/<id>/log` route creates intakes, and
    # `/api/medications/intakes` lists them. Collapsing the two keeps
    # CRUD analysis aligned with how the frontend treats them.
    if url.startswith("/api/medications"):
        return "medications"
    if url.startswith("/api/export"):
        return "export"
    if url.startswith("/api/stats"):
        return "stats"
    if url.startswith("/api/history"):
        return "timeline"
    # Health-record factory endpoints: asthma / defecation / litter / weight /
    # feeding / eye_drops / tooth_brushing / ear_cleaning.
    if any(url.startswith(f"/api/{slug}") for slug in (
        "asthma", "defecation", "litter", "weight", "feeding",
        "eye_drops", "tooth_brushing", "ear_cleaning",
    )):
        return "health_records"
    return "misc"


def audit(routes: list[Route]) -> dict[str, Any]:
    """Build the per-entity CRUD report."""
    by_entity: dict[str, list[Route]] = defaultdict(list)
    for r in routes:
        by_entity[r.entity].append(r)

    report: dict[str, Any] = {}

    expected_crud = {
        "pets":             {"CREATE", "READ_LIST", "READ_ONE", "UPDATE", "DELETE"},
        "users":            {"CREATE", "READ_LIST", "READ_ONE", "UPDATE", "DELETE"},
        "medications":      {"CREATE", "READ_LIST", "READ_ONE", "UPDATE", "DELETE"},
        "health_records":   {"CREATE", "READ_LIST", "READ_ONE", "UPDATE", "DELETE"},
        "auth":             {"CREATE"},   # login only, refresh+logout are session ops
        "export":            set(),        # GET only
        "stats":            set(),         # GET only
        "timeline":         set(),         # GET only
        "misc":             set(),
    }

    for entity, entity_routes in sorted(by_entity.items()):
        ops_present = {r.crud_op for r in entity_routes}
        missing = expected_crud.get(entity, set()) - ops_present

        # Find methods per CRUD op.
        ops_by_method: dict[str, list[Route]] = defaultdict(list)
        for r in entity_routes:
            ops_by_method[r.crud_op].append(r)

        # Detect PUT-vs-PATCH inconsistency for UPDATE.
        update_methods: set[str] = set()
        for r in ops_by_method.get("UPDATE", []):
            update_methods.update(r.methods)

        # Detect routes without auth (excluding known-public endpoints).
        unauth = []
        for r in entity_routes:
            # /api/auth/logout is intentionally public: it must work
            # even when the session is already expired, otherwise the
            # user can't clear their cookies.
            if entity in {"auth"} and r.path in {
                "/api/auth/login", "/api/auth/refresh", "/api/auth/logout",
                "/api/auth/check-admin",
            }:
                continue
            if entity in {"auth"} and r.path.startswith("/login"):
                continue
            if entity in {"misc"} and r.path in {"/favicon.ico", "/", "/dashboard"}:
                continue
            if not r.auth and r.crud_op != "?":
                unauth.append({"path": r.path, "methods": r.methods, "file": r.file, "line": r.line})

        report[entity] = {
            "routes": len(entity_routes),
            "ops_present": sorted(ops_present),
            "ops_missing": sorted(missing),
            "update_methods_used": sorted(update_methods),
            "auth_missing": unauth,
            "details": [
                {
                    "path": r.path,
                    "methods": r.methods,
                    "crud": r.crud_op,
                    "auth": r.auth,
                    "rate_limited": r.rate_limited,
                    "validated": r.validated,
                    "response": r.response_kind,
                    "file": r.file,
                    "line": r.line,
                }
                for r in entity_routes
            ],
        }

    # Cross-entity consistency: do all UPDATE routes use the same HTTP verb?
    inconsistencies: list[str] = []
    for entity, info in report.items():
        methods = info["update_methods_used"]
        if "PATCH" in methods and "PUT" in methods:
            inconsistencies.append(f"{entity}: mixes PUT and PATCH for UPDATE")
        if "PATCH" in methods:
            inconsistencies.append(f"{entity}: uses PATCH instead of PUT (REST convention is PUT for full-resource updates)")

    # Rate limit coverage for login.
    auth_login = next(
        (r for r in routes if r.path == "/api/auth/login"),
        None,
    )
    if auth_login and not auth_login.rate_limited:
        inconsistencies.append("/api/auth/login has no @limiter.limit — brute-force risk")

    return {"by_entity": report, "inconsistencies": inconsistencies}


def main() -> int:
    routes = parse_routes()
    audit_data = audit(routes)

    # Print human-readable summary.
    print("=" * 78)
    print(f"Backend CRUD audit — {len(routes)} routes across {len(audit_data['by_entity'])} entities\n")

    for entity, info in sorted(audit_data["by_entity"].items()):
        print(f"── {entity} ({info['routes']} routes)")
        ops = info["ops_present"]
        print(f"   CRUD ops present:  {', '.join(ops) if ops else '—'}")
        missing = info["ops_missing"]
        if missing:
            print(f"   ⚠ MISSING:         {', '.join(missing)}")
        if info["update_methods_used"]:
            print(f"   UPDATE methods:    {', '.join(info['update_methods_used'])}")
        if info["auth_missing"]:
            print("   ⚠ Routes without auth:")
            for u in info["auth_missing"]:
                print(f"       {','.join(u['methods']):6s} {u['path']}  ({u['file']}:{u['line']})")
        print()

    if audit_data["inconsistencies"]:
        print("=" * 78)
        print("Cross-entity inconsistencies:")
        for i in audit_data["inconsistencies"]:
            print(f"  ⚠ {i}")
        print()

    OUTPUT_PATH.write_text(json.dumps(
        {"routes": [r.to_dict() for r in routes], **audit_data},
        indent=2,
        ensure_ascii=False,
    ))
    print(f"Full JSON → {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())