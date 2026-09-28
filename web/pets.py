"""Pets management routes (API)."""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, make_response, request, url_for
from flask_pydantic_spec import Request, Response

from web.app import api, logger  # shared logger and api
from web.security import login_required, get_current_user
import web.app as app  # to access patched app.db/app.fs in tests
from web import storage
from web.helpers import (
    PRIVATE_IMMUTABLE_CACHE,
    delete_stored_file,
    get_pet_and_validate,
    store_file,
    load_image_variant,
    optimize_image,
    parse_date,
    snap_thumbnail_size,
)
from web.errors import error_response, PetNotFoundDuringDeletion
from web.messages import get_message
from web.builtin_event_types import BUILTIN_TYPE_ORDER
from web.pydantic_helpers import validate_request_data
from web.schemas import (
    PetCreate,
    PetUpdate,
    PetResponseWrapper,
    PetListResponse,
    PetShareRequest,
    PetCreatedResponse,
    PetInviteListResponse,
    PhotoQueryParams,
    SuccessResponse,
    ErrorResponse,
)


pets_bp = Blueprint("pets", __name__)

# Default tiles settings: the most frequent records first (see BUILTIN_TYPE_ORDER).
DEFAULT_TILES_SETTINGS = {
    "order": list(BUILTIN_TYPE_ORDER),
    "visible": {key: True for key in BUILTIN_TYPE_ORDER},
}


def _expose_photo(pet: dict) -> None:
    """Swap the stored file reference for the URL clients load the photo from.

    The reference is a bucket key naming the owner's internal id and the
    storage layout: ours to know, not the client's. The URL carries a
    version token so a new photo is a new URL for the browser cache.
    """
    ref = pet.pop("photo_file_id", None)
    # Only our own photo address goes out. A photo_url a client once wrote
    # could point anywhere and load for everyone the pet is shared with.
    pet.pop("photo_url", None)
    if ref:
        pet["photo_url"] = (
            url_for("pets.get_pet_photo", pet_id=pet["_id"], _external=False) + f"?v={storage.file_version(ref)}"
        )


def _store_pet_photo(photo_file, owner_username: str, pet_id) -> str:
    """Optimise an uploaded photo and put it in object storage; returns its key."""
    optimized = optimize_image(photo_file)
    if not optimized:
        # Not an image Pillow can read. Kept as it came, an HTML or SVG file
        # "photo" was served from our own origin and ran as the viewer.
        raise ValueError("Фото должно быть изображением: JPEG, PNG, WebP или HEIC")
    data, content_type, ext = optimized[0].getvalue(), optimized[1], ".webp"
    return store_file(owner_username, pet_id, "photos", data, content_type, ext)


# Photos stored before non-images were refused may be anything; only these
# are shown inline, the rest is offered as a download.
_INLINE_PHOTO_TYPES = {"image/webp", "image/jpeg", "image/png", "image/gif"}


def get_tiles_settings(pet: dict) -> dict:
    """Get tiles settings from pet, or return default if not set."""
    if pet and pet.get("tiles_settings"):
        return pet["tiles_settings"]
    return DEFAULT_TILES_SETTINGS


def convert_objectid_to_str(obj):
    """Recursively convert all ObjectId instances to strings."""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: convert_objectid_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    return obj


@pets_bp.route("/api/pets", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=PetListResponse), tags=["pets"])
def get_pets():
    """Get list of all pets accessible to current user."""
    # @login_required already guarantees request.current_user is set —
    # get_current_user() here can never actually return an error.
    username, _ = get_current_user()

    pets = list(app.db["pets"].find({"$or": [{"owner": username}, {"shared_with": username}]}).sort("created_at", -1))

    processed_pets = []
    for pet in pets:
        # Convert all ObjectId instances to strings recursively
        pet = convert_objectid_to_str(pet)

        # Ensure _id is string (already converted by convert_objectid_to_str, but double-check)
        pet["_id"] = str(pet["_id"])

        _expose_photo(pet)

        if isinstance(pet.get("birth_date"), datetime):
            pet["birth_date"] = pet["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet.get("created_at"), datetime):
            pet["created_at"] = pet["created_at"].strftime("%Y-%m-%d %H:%M")

        pet["current_user_is_owner"] = pet.get("owner") == username
        # Who's been invited is the owner's business, not the other members'.
        if not pet["current_user_is_owner"]:
            pet.pop("share_invites", None)

        # Ensure tiles_settings is present (use default if missing)
        tiles_settings = get_tiles_settings(pet)
        # Convert any ObjectId in tiles_settings to string
        pet["tiles_settings"] = convert_objectid_to_str(tiles_settings)

        # Convert any ObjectId in shared_with to string (if present)
        if pet.get("shared_with"):
            pet["shared_with"] = [str(uid) if isinstance(uid, ObjectId) else uid for uid in pet["shared_with"]]

        # Final pass: convert any remaining ObjectId instances
        pet = convert_objectid_to_str(pet)

        processed_pets.append(pet)

    return jsonify({"pets": processed_pets})


@pets_bp.route("/api/pets", methods=["POST"])
@login_required
@api.validate(
    body=Request(PetCreate),
    resp=Response(HTTP_201=PetCreatedResponse, HTTP_422=ErrorResponse, HTTP_401=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["pets"],
)
def create_pet():
    """Create a new pet."""
    try:
        # @login_required already guarantees request.current_user is set.
        username = request.current_user

        # Validate request data (supports both JSON and multipart/form-data)
        # For JSON: use request.context.body (validated by @api.validate)
        # For multipart: use validate_request_data helper
        is_multipart = request.content_type and "multipart/form-data" in request.content_type
        if is_multipart:
            # @api.validate(body=Request(PetCreate)) already parses and validates
            # request.form against this same model before this route body ever
            # runs (flask_pydantic_spec.flask_backend.Backend.validate aborts
            # with the request's own validation error otherwise), so the
            # validation_error branch here is unreachable — we only use this
            # call for its parsed `data`.
            data, _ = validate_request_data(request, PetCreate, context="pet creation")
        else:
            # JSON request - already validated by @api.validate(body=Request(PetCreate))
            data = request.context.body  # type: ignore[attr-defined]

        # Handle photo file upload (only for multipart/form-data). The id is
        # chosen up front: the photo's storage key includes it.
        new_pet_id = ObjectId()
        photo_file_id = None
        if is_multipart and "photo_file" in request.files:
            photo_file = request.files["photo_file"]
            if photo_file.filename:
                photo_file_id = _store_pet_photo(photo_file, username, new_pet_id)

        birth_date = parse_date(data.birth_date, allow_future=False)

        pet_data = {
            "_id": new_pet_id,
            "name": data.name,
            "breed": data.breed or "",
            "species": data.species or "",
            "birth_date": birth_date,
            "gender": data.gender or "",
            # None is «не указано», not «нет»: the form shows the difference.
            "is_neutered": data.is_neutered,
            "health_notes": data.health_notes or "",
            "owner": username,
            "shared_with": [],
            "created_at": datetime.now(timezone.utc),
            "created_by": username,
        }

        # A photo only comes as an uploaded file; a client-given URL isn't kept.
        if is_multipart:
            pet_data["photo_file_id"] = photo_file_id

        # Add tiles_settings if provided, otherwise use default
        if data.tiles_settings:
            pet_data["tiles_settings"] = data.tiles_settings.model_dump()
        else:
            pet_data["tiles_settings"] = DEFAULT_TILES_SETTINGS

        result = app.db["pets"].insert_one(pet_data)
        pet_data["_id"] = str(result.inserted_id)
        if isinstance(pet_data.get("birth_date"), datetime):
            pet_data["birth_date"] = pet_data["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet_data.get("created_at"), datetime):
            pet_data["created_at"] = pet_data["created_at"].strftime("%Y-%m-%d %H:%M")

        # Mirror get_pet/get_pets: a photo uploaded on create should come
        # back with a usable photo_url in this same response, not only
        # once the caller re-fetches the pet.
        _expose_photo(pet_data)

        logger.info(f"Pet created: id={pet_data['_id']}, name={pet_data['name']}, owner={username}")
        return get_message("pet_created", status=201, pet=pet_data)

    except storage.StorageNotConfigured:
        return error_response("storage_not_configured")
    except ValueError as e:
        app.logger.warning(f"Invalid input data for pet creation: user={username}, error={e}")
        return error_response("validation_error", str(e))


@pets_bp.route("/api/pets/<pet_id>", methods=["GET"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=PetResponseWrapper,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["pets"],
)
def get_pet(pet_id):
    """Get pet information."""
    try:
        # @login_required already guarantees request.current_user is set.
        username, _ = get_current_user()

        # get_pet_and_validate never returns (None, None) — a falsy pet
        # always comes with an access_error already set.
        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=False)
        if access_error:
            return access_error[0], access_error[1]

        pet["_id"] = str(pet["_id"])
        if isinstance(pet.get("birth_date"), datetime):
            pet["birth_date"] = pet["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet.get("created_at"), datetime):
            pet["created_at"] = pet["created_at"].strftime("%Y-%m-%d %H:%M")

        _expose_photo(pet)

        pet["current_user_is_owner"] = pet.get("owner") == username
        if not pet["current_user_is_owner"]:
            pet.pop("share_invites", None)

        # Ensure tiles_settings is present (use default if missing)
        pet["tiles_settings"] = get_tiles_settings(pet)

        return jsonify({"pet": pet})

    except ValueError as e:
        logger.warning(
            f"Invalid input data for get_pet: id={pet_id}, user={getattr(request, 'current_user', None)}, error={e}"
        )
        return error_response("validation_error", str(e))


@pets_bp.route("/api/pets/<pet_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(PetUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["pets"],
)
def update_pet(pet_id):
    """Update pet information."""
    try:
        # @login_required already guarantees request.current_user is set.
        username, _ = get_current_user()

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        is_multipart = request.content_type and "multipart/form-data" in request.content_type
        if is_multipart:
            # @api.validate(body=Request(PetUpdate)) already parses and validates
            # request.form against this same model before this route body ever
            # runs, so the validation_error branch here is unreachable — we
            # only use this call for its parsed `data`. See the identical
            # comment in create_pet for the full argument.
            data, _ = validate_request_data(request, PetUpdate, context="pet update")
        else:
            # JSON request - already validated by @api.validate(body=Request(PetUpdate))
            data = request.context.body  # type: ignore[attr-defined]

        # Handle photo file upload/removal (only for multipart/form-data)
        #
        # `remove_photo` used to be checked as an `elif` nested inside
        # `if "photo_file" in request.files`, so it only ever ran when a
        # (possibly empty) photo_file part was also present. The
        # frontend never sends that part when removing a photo without
        # picking a new one — so removal silently did nothing. Checking
        # for a real upload (photo_file present AND named) versus a
        # removal request are independent conditions now.
        photo_file_id = pet.get("photo_file_id") if pet else None
        stale_photo_id = None
        if is_multipart:
            photo_file = request.files.get("photo_file")
            if photo_file and photo_file.filename:
                # The old file is only deleted once the pet document points
                # at the new one (after update_one below) — deleting it first
                # left the pet referencing a missing file whenever anything
                # later in this request failed.
                stale_photo_id = pet.get("photo_file_id") if pet else None

                # The photo belongs under the pet owner's prefix, whoever uploads it.
                photo_file_id = _store_pet_photo(photo_file, pet["owner"], pet_id)
            elif request.form.get("remove_photo") == "true":
                stale_photo_id = pet.get("photo_file_id") if pet else None
                photo_file_id = None

        birth_date = parse_date(data.birth_date, allow_future=False)

        # Build update data
        update_data = {}
        if data.name is not None:
            update_data["name"] = data.name.strip() if is_multipart else data.name
        if data.breed is not None:
            update_data["breed"] = data.breed.strip() if is_multipart else data.breed
        if birth_date is not None:
            update_data["birth_date"] = birth_date
        if data.gender is not None:
            update_data["gender"] = data.gender.strip() if is_multipart else data.gender
        if data.species is not None:
            update_data["species"] = data.species.strip() if is_multipart else data.species
        if data.is_neutered is not None:
            update_data["is_neutered"] = data.is_neutered
        if data.health_notes is not None:
            update_data["health_notes"] = data.health_notes.strip() if is_multipart else data.health_notes
        if data.tiles_settings is not None:
            update_data["tiles_settings"] = data.tiles_settings.model_dump()

        # Handle photo fields based on request type
        if is_multipart:
            logger.info(
                f"Photo handling: photo_file_id={photo_file_id}, remove_photo={request.form.get('remove_photo')}"
            )
            # Check remove_photo FIRST - it takes precedence over any photo data
            if request.form.get("remove_photo") == "true":
                # Photo was explicitly removed - clear BOTH fields in database
                update_data["photo_file_id"] = None
                update_data["photo_url"] = None  # Also clear photo_url to remove any leftover blob URLs
                logger.info(f"Setting photo_file_id and photo_url to None for pet {pet_id}")
            elif photo_file_id is not None and photo_file_id != pet.get("photo_file_id"):
                # New photo was uploaded (photo_file_id changed)
                update_data["photo_file_id"] = photo_file_id
        else:
            # JSON request: a photo can only be removed here (a client-given
            # photo_url isn't kept, see _expose_photo).
            if data.remove_photo:
                # Used to only clear the reference, orphaning the GridFS file.
                stale_photo_id = pet.get("photo_file_id") if pet else None
                update_data["photo_file_id"] = None
                update_data["photo_url"] = None

        logger.info(f"Update data for pet {pet_id}: {update_data}")

        if not update_data:
            return error_response("validation_error_no_update_data")

        app.db["pets"].update_one({"_id": ObjectId(pet_id)}, {"$set": update_data})
        if stale_photo_id and stale_photo_id != update_data.get("photo_file_id", photo_file_id):
            try:
                delete_stored_file(stale_photo_id)
            except Exception as e:
                logger.warning(f"Failed to delete old photo: photo_id={stale_photo_id}, pet_id={pet_id}, error={e}")
        logger.info(f"Pet updated: id={pet_id}, user={username}")
        return get_message("pet_updated")

    except storage.StorageNotConfigured:
        return error_response("storage_not_configured")
    except ValueError as e:
        app.logger.warning(f"Invalid pet_id for pet retrieval: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@pets_bp.route("/api/pets/<pet_id>/share", methods=["POST"])
@login_required
@api.validate(
    body=Request(PetShareRequest),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["pets"],
)
def share_pet(pet_id):
    """Invite another user to a pet (owner only).

    An invitation, not access: it takes effect once they accept
    (``/invite/accept``). Handing out access directly let anyone put a pet
    on anyone's account, and with it reminders worded by the sender on
    their devices and the sender inside their «circle».
    """
    try:
        # @login_required already guarantees request.current_user is set.
        username, _ = get_current_user()

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        # `context` is injected by flask-pydantic-spec at runtime; static type checker doesn't know this attribute.
        data = request.context.body  # type: ignore[attr-defined]
        share_username = data.username.strip()

        if not share_username:
            return error_response("validation_error_username_required")

        user = app.db["users"].find_one({"username": share_username, "is_active": True})
        if not user:
            return error_response("user_not_found")

        if share_username == username:
            return error_response("validation_error_self_share")

        shared_with = pet.get("shared_with", []) if pet else []
        if share_username in shared_with:
            return error_response("validation_error_already_shared")
        if share_username in (pet.get("share_invites") or []):
            return error_response("share_already_invited")

        app.db["pets"].update_one({"_id": ObjectId(pet_id)}, {"$addToSet": {"share_invites": share_username}})

        logger.info(f"Pet share invite: id={pet_id}, owner={username}, invited={share_username}")
        return get_message("pet_shared", username=share_username)

    except ValueError as e:
        logger.warning(f"Invalid input data for sharing pet: id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@pets_bp.route("/api/pets/<pet_id>/share/<share_username>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["pets"],
)
def unshare_pet(pet_id, share_username):
    """Remove access from user (owner only)."""
    try:
        # @login_required already guarantees request.current_user is set.
        username, _ = get_current_user()

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        # Takes back access, or an invitation not yet answered.
        app.db["pets"].update_one(
            {"_id": ObjectId(pet_id)}, {"$pull": {"shared_with": share_username, "share_invites": share_username}}
        )

        logger.info(f"Pet unshared: id={pet_id}, owner={username}, unshared_from={share_username}")
        return get_message("pet_unshared", username=share_username)

    except ValueError as e:
        logger.warning(f"Invalid input data for unsharing pet: id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@pets_bp.route("/api/pets/invites", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=PetInviteListResponse), tags=["pets"])
def list_pet_invites():
    """Pets someone has invited the signed-in user to."""
    username = request.current_user
    invites = [
        {
            "pet_id": str(pet["_id"]),
            "pet_name": pet.get("name", ""),
            "species": pet.get("species"),
            "owner": pet["owner"],
        }
        for pet in app.db["pets"].find({"share_invites": username}, {"name": 1, "species": 1, "owner": 1})
    ]
    return jsonify({"invites": invites})


def _answer_invite(pet_id, accept: bool):
    username = request.current_user
    try:
        pet_oid = ObjectId(pet_id)
    except Exception:
        return error_response("share_invite_not_found")
    update = {"$pull": {"share_invites": username}}
    if accept:
        update["$addToSet"] = {"shared_with": username}
    result = app.db["pets"].update_one({"_id": pet_oid, "share_invites": username}, update)
    if result.matched_count == 0:
        return error_response("share_invite_not_found")
    logger.info(f"Pet invite {'accepted' if accept else 'declined'}: id={pet_id}, user={username}")
    return get_message("pet_invite_accepted" if accept else "pet_invite_declined")


@pets_bp.route("/api/pets/<pet_id>/invite/accept", methods=["POST"])
@login_required
@api.validate(resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse), tags=["pets"])
def accept_pet_invite(pet_id):
    """Accept an invitation: the pet appears in the user's list."""
    return _answer_invite(pet_id, accept=True)


@pets_bp.route("/api/pets/<pet_id>/invite/decline", methods=["POST"])
@login_required
@api.validate(resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse), tags=["pets"])
def decline_pet_invite(pet_id):
    """Decline an invitation."""
    return _answer_invite(pet_id, accept=False)


@pets_bp.route("/api/pets/<pet_id>/leave", methods=["POST"])
@login_required
@api.validate(resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse), tags=["pets"])
def leave_pet(pet_id):
    """Stop seeing a pet someone shared: only its owner could end a share before."""
    username = request.current_user
    try:
        pet_oid = ObjectId(pet_id)
    except Exception:
        return error_response("share_not_member")
    result = app.db["pets"].update_one({"_id": pet_oid, "shared_with": username}, {"$pull": {"shared_with": username}})
    if result.matched_count == 0:
        return error_response("share_not_member")
    logger.info(f"Pet left: id={pet_id}, user={username}")
    return get_message("pet_left")


@pets_bp.route("/api/pets/<pet_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["pets"],
)
def delete_pet(pet_id):
    """Delete pet and all related records (cascading delete)."""
    try:
        # @login_required already guarantees request.current_user is set.
        username, _ = get_current_user()

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        if not purge_pet(pet):
            return error_response("pet_not_found")

        logger.info(f"Pet deleted: id={pet_id}, user={username}")
        return get_message("pet_deleted")

    except ValueError as e:
        logger.warning(f"Invalid pet_id for deletion: id={pet_id}, user={username}, error={e}")
        return error_response("invalid_pet_id")


def purge_pet(pet: dict) -> bool:
    """Remove a pet with everything recorded for it and every file it has.

    Shared by deleting one pet and deleting the owner's account. False if
    the pet was already gone.
    """
    pet_id = str(pet["_id"])
    pet_id_obj = ObjectId(pet_id)

    # List of collections with related records to delete.
    # The first eight are the pre-event-engine collections — nothing
    # writes to them anymore, but they're left here as a harmless
    # no-op in case any pet predates the migration and still has
    # rows there. `events` is where every event (builtin or custom
    # type) actually lives today; it was missing from this list
    # until a cascade-delete test caught pet deletion silently
    # leaving a pet's entire event history orphaned.
    collections_to_clean = [
        ("asthma_attacks", {"pet_id": pet_id}),
        ("defecations", {"pet_id": pet_id}),
        ("weights", {"pet_id": pet_id}),
        ("feedings", {"pet_id": pet_id}),
        ("litter_changes", {"pet_id": pet_id}),
        ("eye_drops", {"pet_id": pet_id}),
        ("ear_cleaning", {"pet_id": pet_id}),
        ("tooth_brushing", {"pet_id": pet_id}),
        ("events", {"pet_id": pet_id}),
        ("medication_intakes", {"pet_id": pet_id}),
        ("medications", {"pet_id": pet_id}),
        ("documents", {"pet_id": pet_id}),
    ]

    # Captured before the record goes
    old_photo_id = pet.get("photo_file_id")

    # Documents' files need the same capture-before-delete
    # treatment as the pet photo — the Mongo rows disappear once
    # collections_to_clean runs, so grab their file_ids now.
    doc_file_ids = [
        d["file_id"] for d in app.db["documents"].find({"pet_id": pet_id}, {"file_id": 1}) if d.get("file_id")
    ]

    # Try to use transaction if available
    try:
        with app.db.client.start_session() as session:
            with session.start_transaction():
                # Delete all related records
                total_deleted = 0
                for collection_name, query in collections_to_clean:
                    result = app.db[collection_name].delete_many(query, session=session)
                    if result.deleted_count > 0:
                        logger.info(f"Deleted {result.deleted_count} records from {collection_name} for pet {pet_id}")
                        total_deleted += result.deleted_count

                # Delete the pet itself
                result = app.db["pets"].delete_one({"_id": pet_id_obj}, session=session)

                if result.deleted_count == 0:
                    raise PetNotFoundDuringDeletion("Pet not found during deletion")

                logger.info(f"Pet deleted with transaction: id={pet_id}, total_related_records={total_deleted}")
    except Exception as tx_error:
        # Fallback for standalone MongoDB (no replica set) or mongomock
        error_msg = str(tx_error).lower()
        if "transaction" in error_msg or "replica" in error_msg or "session" in error_msg or "mongomock" in error_msg:
            logger.warning(f"Transactions not supported, using fallback cascading delete: {tx_error}")

            # Delete pet first, then related records (prevents foreign key issues)
            result = app.db["pets"].delete_one({"_id": pet_id_obj})

            if result.deleted_count == 0:
                return False

            # Best-effort deletion of related records
            total_deleted = 0
            failed_collections = []
            for collection_name, query in collections_to_clean:
                try:
                    result = app.db[collection_name].delete_many(query)
                    if result.deleted_count > 0:
                        logger.info(f"Deleted {result.deleted_count} records from {collection_name} for pet {pet_id}")
                        total_deleted += result.deleted_count
                except Exception as col_error:
                    logger.error(f"Failed to delete from {collection_name} for pet {pet_id}: {col_error}")
                    failed_collections.append(collection_name)

            if failed_collections:
                logger.warning(
                    f"Some related records may not have been deleted for pet {pet_id}: {', '.join(failed_collections)}"
                )

            logger.info(f"Pet deleted (fallback): id={pet_id}, total_related_records={total_deleted}")
        else:
            # Re-raise if it's not a transaction-related error
            raise

    # Delete the photo (outside the transaction: storage isn't part of it)
    if old_photo_id:
        try:
            delete_stored_file(old_photo_id)
            logger.info(f"Deleted photo {old_photo_id} for pet {pet_id}")
        except Exception as photo_error:
            # Log but don't fail the request
            logger.warning(f"Failed to delete photo {old_photo_id} for pet {pet_id}: {photo_error}")

    # Same rationale: files live outside the database and its transaction.
    for file_id in doc_file_ids:
        try:
            delete_stored_file(file_id)
        except Exception as file_error:
            logger.warning(f"Failed to delete document file {file_id} for pet {pet_id}: {file_error}")

    # Unconfirmed scan uploads, and anything else left under the pet's
    # prefix (thumbnails, an object whose record write failed).
    app.db["document_uploads"].delete_many({"pet_id": pet_id})
    if storage.storage_configured():
        try:
            storage.delete_prefix(storage.pet_prefix(app.db, pet["owner"], pet_id))
        except Exception as prefix_error:
            logger.warning(f"Failed to clear stored files for pet {pet_id}: {prefix_error}")

    return True


@pets_bp.route("/api/pets/<pet_id>/photo", methods=["GET"])
@login_required
@api.validate(
    query=PhotoQueryParams,
    resp=Response(
        HTTP_200=None,
        HTTP_422=ErrorResponse,
        HTTP_401=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["pets"],
)
def get_pet_photo(pet_id):
    """Get pet photo file with optional resizing."""
    try:
        # @login_required already guarantees request.current_user is set.
        username = request.current_user

        pet = app.db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return error_response("pet_not_found")

        if pet.get("owner") != username and username not in pet.get("shared_with", []):
            return error_response("pet_forbidden")

        photo_file_id = pet.get("photo_file_id")
        if not photo_file_id:
            return error_response("photo_not_found")

        # Get optional width and height for resizing
        width = snap_thumbnail_size(request.args.get("w", type=int))
        height = snap_thumbnail_size(request.args.get("h", type=int))

        etag = f"{storage.file_version(photo_file_id)}_{width}_{height}"
        if request.if_none_match.contains(etag):
            # Same file id + size means the same bytes — skip the GridFS read
            # and the resize entirely.
            response = make_response("", 304)
            response.set_etag(etag)
            response.headers.set("Cache-Control", PRIVATE_IMMUTABLE_CACHE)
            return response

        try:
            photo_data, content_type = load_image_variant(photo_file_id, width, height)

            response = make_response(photo_data)
            if content_type in _INLINE_PHOTO_TYPES:
                response.headers.set("Content-Type", content_type)
                response.headers.set("Content-Disposition", "inline")
            else:
                response.headers.set("Content-Type", "application/octet-stream")
                response.headers.set("Content-Disposition", "attachment")
            response.headers.set("Cache-Control", PRIVATE_IMMUTABLE_CACHE)
            response.set_etag(etag)
            logger.info(f"Pet photo retrieved: pet_id={pet_id}, user={username}, size={width}x{height}")
            return response
        except Exception as e:
            logger.error(f"Error retrieving pet photo: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
            return error_response("upload_error")

    except (InvalidId, TypeError, ValueError) as e:
        logger.warning(
            f"Invalid pet_id for photo: id={pet_id}, user={getattr(request, 'current_user', None)}, error={e}"
        )
        return error_response("invalid_pet_id")
