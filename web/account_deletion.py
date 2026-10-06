"""Deleting a user's own account, and everything that goes with it.

A pet someone else also looks after isn't deleted with its owner: it goes
to the first person it's shared with (the one still able to sign in, if
any), files and all. A pet nobody else has is deleted with its records
and files. What the user wrote on other people's pets stays there, with
the author taken off: the login can be registered again by someone else,
and their name mustn't end up on the old records.
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId

import web.app as app
from web import storage
from web.app import logger

# The records that carry the login of whoever made them.
AUTHORED_COLLECTIONS = ("events", "medication_intakes", "medications", "documents", "medical_records", "medical_shares")
# The user's own rows elsewhere: sessions, links in letters, devices.
PERSONAL_COLLECTIONS = ("refresh_tokens", "account_tokens", "push_subscriptions")


def was_deleted(username: str) -> bool:
    """Whether this login belonged to an account that was deleted for good.

    The first DELETE went through and its answer was lost on the way (a closed
    tab, a dead connection), so the person pressed the button again. All that is
    kept is the login itself and when it went: nothing about the account, and
    no password hash to check a wrong guess against. A login that has been
    registered again belongs to the new person, so the account has to be gone
    for this to answer.
    """
    if app.db.users.find_one({"username": username}, {"_id": 1}):
        return False
    return app.db.deleted_accounts.find_one({"username": username}, {"_id": 1}) is not None


def _heir(pet: dict) -> Optional[str]:
    """Who gets the pet: the first member who can still sign in, else the
    first who has an account at all; None if nobody."""
    members = [m for m in pet.get("shared_with") or [] if m and m != pet.get("owner")]
    if not members:
        return None
    accounts = {
        u["username"]: u for u in app.db.users.find({"username": {"$in": members}}, {"username": 1, "is_active": 1})
    }
    for member in members:
        if member in accounts and accounts[member].get("is_active") is not False:
            return member
    return next((member for member in members if member in accounts), None)


def deletion_plan(username: str) -> dict:
    """What deleting ``username`` would do to pets: which are deleted,
    which go to whom, which the user just stops seeing."""
    deleted, transferred = [], []
    for pet in app.db.pets.find({"owner": username}).sort("created_at", 1):
        heir = _heir(pet)
        if heir:
            transferred.append((pet, heir))
        else:
            deleted.append(pet)
    left = list(app.db.pets.find({"shared_with": username, "owner": {"$ne": username}}).sort("created_at", 1))
    return {"deleted": deleted, "transferred": transferred, "left": left}


def plan_summary(plan: dict) -> dict:
    """The plan as the API shows it."""
    return {
        "deleted": [{"id": str(p["_id"]), "name": p.get("name", "")} for p in plan["deleted"]],
        "transferred": [
            {"id": str(p["_id"]), "name": p.get("name", ""), "new_owner": heir} for p, heir in plan["transferred"]
        ],
        "left": [{"id": str(p["_id"]), "name": p.get("name", ""), "owner": p.get("owner")} for p in plan["left"]],
    }


def _moved_key(ref, old_prefix: str, new_prefix: str):
    """Copy a stored file from the old owner's folder to the new owner's;
    the new key, or ``ref`` itself when it isn't in that folder (a legacy
    GridFS id, or no file)."""
    if not ref or not storage.is_storage_key(ref) or not str(ref).startswith(old_prefix):
        return ref
    new_ref = new_prefix + str(ref)[len(old_prefix) :]
    storage.copy_object(ref, new_ref)
    return new_ref


def _copy_files(username: str, transferred: list) -> dict:
    """Copy every file of the pets being handed over to the heirs' folders.

    Runs before anything in the database changes: if the file store fails
    here, the account stays as it was. Returns {old key: new key}; thumbnails
    aren't copied, they're made again on the first view.
    """
    moves = {}
    if not storage.storage_configured():
        return moves
    for pet, heir in transferred:
        pet_id = str(pet["_id"])
        old_prefix = storage.pet_prefix(app.db, username, pet_id)
        new_prefix = storage.pet_prefix(app.db, heir, pet_id)
        refs = [pet.get("photo_file_id")]
        refs += [d.get("file_id") for d in app.db.documents.find({"pet_id": pet_id}, {"file_id": 1})]
        for ref in refs:
            new_ref = _moved_key(ref, old_prefix, new_prefix)
            if new_ref != ref:
                moves[ref] = new_ref
    return moves


def _hand_over(username: str, pet: dict, heir: str, moves: dict) -> None:
    pet_id = str(pet["_id"])
    update = {
        "$set": {
            "owner": heir,
            "shared_with": [m for m in pet.get("shared_with") or [] if m not in (heir, username)],
            "share_invites": [m for m in pet.get("share_invites") or [] if m not in (heir, username)],
        },
        "$unset": {"created_by": ""},
    }
    if pet.get("photo_file_id") in moves:
        update["$set"]["photo_file_id"] = moves[pet["photo_file_id"]]
    app.db.pets.update_one({"_id": pet["_id"]}, update)
    for doc in app.db.documents.find({"pet_id": pet_id}, {"file_id": 1}):
        if doc.get("file_id") in moves:
            app.db.documents.update_one({"_id": doc["_id"]}, {"$set": {"file_id": moves[doc["file_id"]]}})
    # Scans half-way through uploading went to the old owner's folder,
    # which is about to go.
    app.db.document_uploads.delete_many({"pet_id": pet_id})
    logger.info(f"Pet handed over: id={pet_id}, from={username}, to={heir}")


def _settle_event_types(username: str, remaining_pet_ids: list) -> None:
    """The user's own record types: a type still used on a pet that stays
    goes to that pet's owner (or its records couldn't be shown); an unused
    one is removed."""
    for event_type in app.db.event_types.find({"created_by": username, "is_builtin": {"$ne": True}}):
        used = app.db.events.find_one({"type": event_type["key"], "pet_id": {"$in": remaining_pet_ids}}, {"pet_id": 1})
        pet = None
        if used:
            try:
                pet = app.db.pets.find_one({"_id": ObjectId(used["pet_id"])}, {"owner": 1})
            except (InvalidId, TypeError):
                pet = None
        if pet and pet.get("owner") and pet["owner"] != username:
            app.db.event_types.update_one({"_id": event_type["_id"]}, {"$set": {"created_by": pet["owner"]}})
        else:
            app.db.event_types.delete_one({"_id": event_type["_id"]})


def delete_account(username: str) -> dict:
    """Delete ``username`` for good. Returns the plan that was carried out.

    Raises if the file store fails while copying the handed-over pets'
    files; nothing has changed at that point.
    """
    from web.pets import purge_pet

    plan = deletion_plan(username)
    # Worked out while the user still exists: the folder is named by their id.
    own_folder = storage.user_prefix(app.db, username)

    moves = _copy_files(username, plan["transferred"])

    for pet, heir in plan["transferred"]:
        _hand_over(username, pet, heir, moves)
    for pet in plan["deleted"]:
        purge_pet(pet)

    # Other people's pets: no more access, and no pending invitations.
    app.db.pets.update_many(
        {"$or": [{"shared_with": username}, {"share_invites": username}]},
        {"$pull": {"shared_with": username, "share_invites": username}},
    )

    remaining_pet_ids = [str(p["_id"]) for p, _ in plan["transferred"]] + [str(p["_id"]) for p in plan["left"]]
    for name in AUTHORED_COLLECTIONS:
        app.db[name].update_many(
            {"pet_id": {"$in": remaining_pet_ids}, "username": username}, {"$set": {"username": ""}}
        )
    _settle_event_types(username, remaining_pet_ids)

    for name in PERSONAL_COLLECTIONS:
        app.db[name].delete_many({"username": username})
    app.db.users.delete_one({"username": username})
    # A repeat of this DELETE answers as if it had just been done (see
    # was_deleted). Not one of PERSONAL_COLLECTIONS: it holds no data of the
    # account, only that this login is free again.
    app.db.deleted_accounts.update_one(
        {"username": username},
        {"$set": {"username": username, "deleted_at": datetime.now(timezone.utc)}},
        upsert=True,
    )

    # Last, so a failure here leaves stray files and not a half-deleted account.
    if storage.storage_configured():
        try:
            storage.delete_prefix(own_folder)
        except Exception as e:
            logger.warning(f"Files of a deleted account not cleared: user={username}, error={e}")

    logger.info(
        f"Account deleted: user={username}, pets_deleted={len(plan['deleted'])}, "
        f"pets_handed_over={len(plan['transferred'])}, pets_left={len(plan['left'])}"
    )
    return plan
