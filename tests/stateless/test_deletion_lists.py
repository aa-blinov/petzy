"""The deletion lists must not fall behind the collections that exist.

A new collection is easy to add and easy to forget: `pets.py` and
`account_deletion.py` clean up by hand-written names, and nothing noticed
when `document_uploads` was left out of both. This test takes the list of
collections from where the app itself declares them (`web/db.py`, the module
that indexes every collection and documents what it is for) and asks the
question for each one: when a pet is deleted, or when an account is deleted,
what happens to its rows? The answer has to be in a list, or in
`HELD_ELSEWHERE` below with the reason written down.

A collection that is added to `db.py` and to no list and to no exception
fails here, which is the point.
"""

import ast
import re
from pathlib import Path

import pytest

from web.account_deletion import AUTHORED_COLLECTIONS, PERSONAL_COLLECTIONS

ROOT = Path(__file__).resolve().parents[2]
DB_PY = ROOT / "web" / "db.py"
PETS_PY = ROOT / "web" / "pets.py"

# Collections no deletion list has to mention, and why each one is safe.
# A name here is a decision, not a gap: if a new collection lands, it does
# not get in here by accident.
HELD_ELSEWHERE = {
    "pets": "the row itself: `purge_pet`, or the pet is handed over and stays",
    "users": "the account row itself, deleted by login",
    "event_types": "custom types are settled by `_settle_event_types`: to the new owner or gone",
    "deleted_accounts": "only the login and when it went, so a repeated DELETE answers right; no data",
    "image_thumbnails": "variants of a stored file; dropped with the file, and a TTL-free leftover costs nothing",
    "medication_reminders_sent": "a dedupe row for one reminder slot; `purge_at` TTL drops it",
    "document_expiry_reminders_sent": "a dedupe row for one expiry date; `purge_at` TTL drops it",
    "medical_due_reminders_sent": "a dedupe row for one repeat stage; `purge_at` TTL drops it",
}


def _declared_collections() -> set[str]:
    """Every collection `web/db.py` names: the ones it indexes and the ones
    it gives a compound index through `HEALTH_RECORD_COLLECTIONS`."""
    source = DB_PY.read_text()
    tree = ast.parse(source)
    names = {m.group(1) for m in re.finditer(r"\bdb\.([a-z_][a-z0-9_]*)", source)}
    names |= {m.group(1) for m in re.finditer(r"""\bdb\[\s*['"]([a-z_][a-z0-9_]*)['"]\s*\]""", source)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "HEALTH_RECORD_COLLECTIONS" for t in node.targets
        ):
            names |= set(ast.literal_eval(node.value))
    # `db.py` talks about the database object itself, not collections.
    return names - {"db", "name", "client", "list_collection_names"}


def _collections_cleaned_with_a_pet() -> set[str]:
    """The names in `collections_to_clean` in `purge_pet` (web/pets.py)."""
    tree = ast.parse(PETS_PY.read_text())
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not any(
            isinstance(t, ast.Name) and t.id == "collections_to_clean" for t in node.targets
        ):
            continue
        for entry in node.value.elts:
            # Only the name: the query next to it holds `pet_id`, a variable,
            # so the entry can't be evaluated as a whole.
            found.add(entry.elts[0].value)
    assert found, "collections_to_clean not found in web/pets.py"
    return found


DECLARED = _declared_collections()
PET_CLEANED = _collections_cleaned_with_a_pet()
ACCOUNT_CLEANED = set(AUTHORED_COLLECTIONS) | set(PERSONAL_COLLECTIONS)


@pytest.mark.parametrize("collection", sorted(DECLARED))
def test_every_collection_is_accounted_for(collection):
    """Every declared collection is cleaned with a pet, or with the account,
    or written down in HELD_ELSEWHERE."""
    assert collection in PET_CLEANED or collection in ACCOUNT_CLEANED or collection in HELD_ELSEWHERE, (
        f"{collection}: not in collections_to_clean, AUTHORED_COLLECTIONS or PERSONAL_COLLECTIONS, and not in HELD_ELSEWHERE"
    )


def test_the_list_of_exceptions_has_no_strangers():
    """An exception that no longer names a real collection is a leftover
    decision, and would let a future collection of that name slip through
    unexamined."""
    assert not (set(HELD_ELSEWHERE) - DECLARED), "HELD_ELSEWHERE names collections web/db.py doesn't declare"


def test_the_lists_name_no_collection_that_does_not_exist():
    """A name in a deletion list that nothing declares is a typo: the rows
    it was meant to remove are still there."""
    stray = (PET_CLEANED | ACCOUNT_CLEANED) - DECLARED
    assert not stray, f"cleaned but never declared in web/db.py: {sorted(stray)}"


def test_the_health_records_are_all_deleted_with_their_pet():
    """Each per-type health collection is reached by the same queries as
    `events`, so a pet purge that skipped one of them would leave history
    behind with no way to show it."""
    from web.db import HEALTH_RECORD_COLLECTIONS

    missing = [name for name in HEALTH_RECORD_COLLECTIONS if name not in PET_CLEANED]
    assert not missing, f"health record collections not in collections_to_clean: {missing}"
