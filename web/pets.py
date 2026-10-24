"""Pets management routes (API)."""

import uuid
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError
from flask import Blueprint, g, jsonify, make_response, request, url_for
from flask_pydantic_spec import Request, Response

from web.app import api, logger  # shared logger and api
from web.decorators import pat_allowed
from web.security import login_required, get_current_user
import web.app as app  # to access patched app.db/app.fs in tests
from web import storage
from web.account_deletion import _heir
from web.helpers import (
    LIVE_EVENT_FILTER,
    PRIVATE_IMMUTABLE_CACHE,
    delete_stored_file,
    get_pet_and_validate,
    store_file,
    load_image_variant,
    optimize_image,
    parse_date,
    snap_thumbnail_size,
)
from web.errors import error_response, PetDeletionFailed, PetNotFoundDuringDeletion
from web.picture_links import picture_route, signed_picture_url
from web.messages import get_message
from web.builtin_event_types import BUILTIN_TYPE_ORDER
from web.pydantic_helpers import validate_request_data
from web.schemas import (
    PetCreate,
    PetDeletionImpactResponse,
    PetUpdate,
    PetResponseWrapper,
    PetListResponse,
    PetShareRequest,
    PetFormDefaults,
    PetFormDefaultsResponse,
    PetLook,
    PetLookResponse,
    PetCreatedResponse,
    PetInviteListResponse,
    PhotoQueryParams,
    SuccessResponse,
    ErrorResponse,
)
from web.idempotency import idempotent
from web.offline import (
    conflict_answer,
    deleted_by_id_answer,
    deleted_by_local_id_answer,
    is_stale,
    record_version,
    require_local_record_access,
    version_guard,
)
from web.sync import log_deletion, now_utc, pet_viewers
from web.helpers import utc_iso


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
        pet_id, version = str(pet["_id"]), storage.file_version(ref)
        # Signed for the person asking, and absolute: a native app loads it without the headers of its session.
        address = signed_picture_url(
            url_for("pets.get_pet_photo", pet_id=pet_id, _external=False), "pet-photo", pet_id, version, f"v={version}"
        )
        if address:
            pet["photo_url"] = address


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


def _expose_next_owner(pet: dict, username: str) -> None:
    """To the owner only: who becomes the owner if they delete their account (the first of the family still able to sign in)."""
    if pet.get("owner") == username:
        pet["next_owner"] = _heir(pet)
    else:
        pet.pop("next_owner", None)


def get_tiles_settings(pet: dict) -> dict:
    """Get tiles settings from pet, or return default if not set."""
    if pet and pet.get("tiles_settings"):
        return pet["tiles_settings"]
    return DEFAULT_TILES_SETTINGS


def _trimmed(value: str | None) -> str | None:
    """A text field without the spaces around it — the one rule every path applies.

    The breed and the health notes used to be trimmed only on a multipart edit:
    the same words reached the card with and without the spaces the phone form
    adds, and a JSON client kept them.
    """
    return value.strip() if value is not None else None


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
@pat_allowed("pets:read")
@api.validate(resp=Response(HTTP_200=PetListResponse), tags=["pets"])
def get_pets():
    """Get list of all pets accessible to current user.

    Newest first. Each entry says whether the signed-in person owns the pet, and
    that flag decides what may be changed from here. Who was invited is the owner's
    business: it goes to the owner and to nobody else.
    """
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
            pet["created_at"] = utc_iso(pet["created_at"])
        # The version an edit is made from, in the same format as every other timestamp.
        pet["updated_at"] = record_version(pet) or None

        pet["current_user_is_owner"] = pet.get("owner") == username
        # Who's been invited is the owner's business, not the other members'.
        if not pet["current_user_is_owner"]:
            pet.pop("share_invites", None)
        _expose_next_owner(pet, username)

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


def _pet_named(local_id: str) -> dict | None:
    """The pet the device named with ``local_id``. A name is unique on the stand, so there is at most one."""
    return app.db["pets"].find_one({"local_id": local_id})


def _created_view(pet: dict) -> dict:
    """A pet as the answer to its creation says it: the same fields whether it was just made or made earlier."""
    pet = dict(pet)
    pet["_id"] = str(pet["_id"])
    if isinstance(pet.get("birth_date"), datetime):
        pet["birth_date"] = pet["birth_date"].strftime("%Y-%m-%d")
    if isinstance(pet.get("created_at"), datetime):
        pet["created_at"] = utc_iso(pet["created_at"])
    pet["updated_at"] = record_version(pet) or None
    # Mirror get_pet/get_pets: a photo uploaded on create should come
    # back with a usable photo_url in this same response, not only
    # once the caller re-fetches the pet.
    _expose_photo(pet)
    return pet


def _answer_for_pet_name(existing: dict | None, username: str, local_id: str):
    """The answer to a create that names a pet: the one already there (200), or why the name cannot be used.

    The caller's own pet: answered as saved, and nothing is written. Somebody else's pet holds the name: 409
    ``local_id_taken``. No pet, but a deleted one had the name: 409 ``record_deleted``.
    """
    if existing is None:
        return deleted_by_local_id_answer("pet", local_id, username)
    if existing.get("owner") != username:
        return error_response("local_id_taken")
    return get_message("pet_created", status=200, pet=_created_view(existing))


@pets_bp.route("/api/pets", methods=["POST"])
@login_required
@api.validate(
    body=Request(PetCreate),
    resp=Response(
        HTTP_201=PetCreatedResponse,
        HTTP_409=ErrorResponse,
        HTTP_422=ErrorResponse,
        HTTP_401=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["pets"],
)
@idempotent
def create_pet():
    """Create a new pet.

    The caller becomes the owner and the pet starts shared with nobody. A photo
    sent in the same request is converted to WebP, at most 1920 px on the longer side; a file that is not a
    picture is refused (422). A birth date in the future or more than 50 years back is refused. A ``local_id`` the device gives makes the request repeatable: sent again, it is answered with the pet it already made (200) and nothing is written twice, the photo included; a name that belongs to another person's pet is 409 ``local_id_taken``, and a name of a pet that was deleted is 409 ``record_deleted``.
    """
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

        if data.local_id:
            # The device names the pet itself, so the name decides: the same request sent again is the pet that is
            # already there, and its photo is not stored a second time.
            answer = _answer_for_pet_name(_pet_named(data.local_id), username, data.local_id)
            if answer:
                return answer

        # Handle photo file upload (only for multipart/form-data). The id is
        # chosen up front: the photo's storage key includes it.
        new_pet_id = ObjectId()
        photo_file_id = None
        # Read before the photo is stored: a date that is refused (422) must not leave a file in the storage.
        birth_date = parse_date(data.birth_date, allow_future=False, tz=data.tz)
        if is_multipart and "photo_file" in request.files:
            photo_file = request.files["photo_file"]
            if photo_file.filename:
                photo_file_id = _store_pet_photo(photo_file, username, new_pet_id)

        pet_data = {
            "_id": new_pet_id,
            "name": data.name,
            "breed": _trimmed(data.breed) or "",
            "species": data.species or "",
            "birth_date": birth_date,
            "gender": data.gender or "",
            # None is «не указано», not «нет»: the form shows the difference.
            "is_neutered": data.is_neutered,
            "health_notes": _trimmed(data.health_notes) or "",
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

        pet_data["updated_at"] = now_utc()
        if data.local_id:
            pet_data["local_id"] = data.local_id
        try:
            app.db["pets"].insert_one(pet_data)
        except DuplicateKeyError:
            # Two requests naming one pet at the same moment: the second one finds what the first one wrote, and the
            # photo it stored is not needed.
            if photo_file_id:
                delete_stored_file(photo_file_id)
            answer = _answer_for_pet_name(_pet_named(data.local_id or ""), username, data.local_id or "")
            if not data.local_id or not answer:
                raise
            return answer
        except Exception:
            # The pet was not written: its photo must not stay behind with no owner.
            if photo_file_id:
                delete_stored_file(photo_file_id)
            raise
        pet_data = _created_view(pet_data)

        logger.info(f"Pet created: id={pet_data['_id']}, owner={username}")
        return get_message("pet_created", status=201, pet=pet_data)

    except storage.StorageNotConfigured:
        return error_response("storage_not_configured")
    except ValueError as e:
        app.logger.warning(f"Invalid input data for pet creation: user={username}, error={e}")
        return error_response("validation_error", str(e))


def _pet_view(pet: dict, username: str) -> dict:
    """A pet as the detail endpoint reads it: also what a rejected edit brings back as ``record``."""
    pet = dict(pet)
    pet["_id"] = str(pet["_id"])
    if isinstance(pet.get("birth_date"), datetime):
        pet["birth_date"] = pet["birth_date"].strftime("%Y-%m-%d")
    if isinstance(pet.get("created_at"), datetime):
        pet["created_at"] = utc_iso(pet["created_at"])
    # The version an edit is made from, in the same format as every other timestamp.
    pet["updated_at"] = record_version(pet) or None

    _expose_photo(pet)

    pet["current_user_is_owner"] = pet.get("owner") == username
    if not pet["current_user_is_owner"]:
        pet.pop("share_invites", None)
    _expose_next_owner(pet, username)

    # Ensure tiles_settings is present (use default if missing)
    pet["tiles_settings"] = get_tiles_settings(pet)
    return pet


@pets_bp.route("/api/pets/<pet_id>", methods=["GET"])
@login_required
@pat_allowed("pets:read")
@api.validate(
    resp=Response(HTTP_200=PetResponseWrapper, HTTP_422=ErrorResponse, HTTP_404=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["pets"],
)
def get_pet(pet_id):
    """Get pet information.

    Readable by everyone the pet is shared with. A pet the signed-in person has
    nothing to do with answers exactly like a missing one, so an address cannot be
    used to find out whether somebody else's pet exists.
    """
    try:
        # @login_required already guarantees request.current_user is set.
        username, _ = get_current_user()

        # get_pet_and_validate never returns (None, None) — a falsy pet
        # always comes with an access_error already set.
        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=False)
        if access_error:
            return access_error[0], access_error[1]

        return jsonify({"pet": _pet_view(pet, username)})

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
        HTTP_409=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["pets"],
)
def update_pet(pet_id):
    """Update pet information.

    The owner only. Anyone the pet is shared with may read it but is told that the
    action is the owner's. Fields left out keep their value, and ``remove_photo``
    drops the photo without touching the rest. An empty ``birth_date`` keeps the date
    rather than clearing it. A new photo is handled as at creation. A body that changes nothing answers
    422 ``validation_error_no_update_data``. ``base_version`` is the ``updated_at`` the device last read: a pet
    changed since answers 409 ``conflict`` with the pet as it is now in ``record``, and nothing is stored, a photo
    included; without it the change is applied. A pet that was deleted answers 409 ``record_deleted``.
    """
    # @login_required already guarantees request.current_user is set.
    username, _ = get_current_user()

    try:
        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
    except ValueError as e:
        app.logger.warning(f"Invalid pet_id for pet retrieval: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))
    if access_error:
        return deleted_by_id_answer("pet", pet_id, username) or (access_error[0], access_error[1])
    return _update_pet(pet, username)


@pets_bp.route("/api/pets/local/<local_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(PetUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_409=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["pets"],
)
@require_local_record_access("pets", "pet", owner_only=True)
def update_pet_by_local_id(local_id):
    """Update a pet by the ``local_id`` the device gave it, for when the device has not got the pet's id.

    The same update as by id, for the owner, with the same ``base_version`` check. The name stays as it was created.
    """
    return _update_pet(g.record, g.username)


def _update_pet(pet: dict, username: str):
    """The update of one pet found by the access check, by its id or by the local_id the device named."""
    pet_id = str(pet["_id"])
    uploaded_photo_id = None  # the file this request stored: it is deleted unless the request ends in a write
    written = False
    try:
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

        # Before anything is stored: a refused edit leaves no photo behind.
        if is_stale(data.base_version, pet):
            return conflict_answer(_pet_view(pet, username))

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
        # Read before a new photo is stored: a date that is refused (422) must not leave a file in the storage.
        birth_date = parse_date(data.birth_date, allow_future=False, tz=data.tz)
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
                uploaded_photo_id = photo_file_id
            elif request.form.get("remove_photo") == "true":
                stale_photo_id = pet.get("photo_file_id") if pet else None
                photo_file_id = None

        # Build update data
        update_data = {}
        if data.name is not None:
            update_data["name"] = data.name.strip() if is_multipart else data.name
        if data.breed is not None:
            update_data["breed"] = _trimmed(data.breed)
        if birth_date is not None:
            update_data["birth_date"] = birth_date
        if data.gender is not None:
            update_data["gender"] = data.gender.strip() if is_multipart else data.gender
        if data.species is not None:
            update_data["species"] = data.species.strip() if is_multipart else data.species
        if data.is_neutered is not None:
            update_data["is_neutered"] = data.is_neutered
        if data.health_notes is not None:
            update_data["health_notes"] = _trimmed(data.health_notes)
        if data.tiles_settings is not None:
            update_data["tiles_settings"] = data.tiles_settings.model_dump()

        # Handle photo fields based on request type. The crops of the look are parts of the photo they were cut from:
        # a photo that is replaced or removed takes them away, or the next photo would show a stranger's framing.
        photo_changed = False
        if is_multipart:
            logger.info(
                f"Photo handling: photo_file_id={photo_file_id}, remove_photo={request.form.get('remove_photo')}"
            )
            # Check remove_photo FIRST - it takes precedence over any photo data
            if request.form.get("remove_photo") == "true":
                # Photo was explicitly removed - clear BOTH fields in database
                update_data["photo_file_id"] = None
                update_data["photo_url"] = None  # Also clear photo_url to remove any leftover blob URLs
                photo_changed = True
                logger.info(f"Setting photo_file_id and photo_url to None for pet {pet_id}")
            elif photo_file_id is not None and photo_file_id != pet.get("photo_file_id"):
                # New photo was uploaded (photo_file_id changed)
                update_data["photo_file_id"] = photo_file_id
                photo_changed = True
        else:
            # JSON request: a photo can only be removed here (a client-given
            # photo_url isn't kept, see _expose_photo).
            if data.remove_photo:
                # Used to only clear the reference, orphaning the GridFS file.
                stale_photo_id = pet.get("photo_file_id") if pet else None
                update_data["photo_file_id"] = None
                update_data["photo_url"] = None
                photo_changed = True

        # Field names only: the values are the owner's own data, health notes among them.
        logger.info(f"Update data for pet {pet_id}: fields={sorted(update_data)}")

        if not update_data:
            return error_response("validation_error_no_update_data")

        update_data["updated_at"] = now_utc()
        update = {"$set": update_data}
        if photo_changed:
            update["$unset"] = {"look.crops": ""}
        result = app.db["pets"].update_one({"_id": ObjectId(pet_id), **version_guard(pet, data.base_version)}, update)
        if result.matched_count == 0:
            # Saved by someone else (or deleted) between the check above and the write: the new photo is not needed.
            if photo_file_id and photo_file_id != pet.get("photo_file_id"):
                delete_stored_file(photo_file_id)
            latest = app.db["pets"].find_one({"_id": ObjectId(pet_id)})
            if latest is None:
                return error_response("record_deleted")
            return conflict_answer(_pet_view(latest, username))
        written = True
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
    finally:
        if uploaded_photo_id and not written:
            try:
                delete_stored_file(uploaded_photo_id)
            except Exception as e:
                logger.warning(
                    f"Failed to delete unused photo: photo_id={uploaded_photo_id}, pet_id={pet_id}, error={e}"
                )


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
    (``/invite/accept``). ``username`` is the exact login, case included (as GET /api/users/search returns it);
    a switched-off account answers the same 404 ``user_not_found`` as a missing one. 422 codes:
    ``validation_error_username_required`` (blank), ``validation_error_self_share``,
    ``validation_error_already_shared`` (already a member) and ``share_already_invited``. Handing out access directly let anyone put a pet
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

        app.db["pets"].update_one(
            {"_id": ObjectId(pet_id)},
            {"$addToSet": {"share_invites": share_username}, "$set": {"updated_at": now_utc()}},
        )

        logger.info(f"Pet share invite: id={pet_id}, owner={username}, invited={share_username}")
        return get_message("pet_shared", username=share_username)

    except ValueError as e:
        logger.warning(f"Invalid input data for sharing pet: id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@pets_bp.route("/api/pets/<pet_id>/share/<share_username>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_404=ErrorResponse,
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["pets"],
)
def unshare_pet(pet_id, share_username):
    """Remove access from user (owner only).

    Takes back the access and, if the invitation was never answered, the invitation with
    it. Nothing is deleted: the person keeps their own account and nothing of the pet
    goes with them. Only the owner can do this, and only for a pet they own. A login that had
    neither access nor an invitation still answers 200.
    """
    try:
        # @login_required already guarantees request.current_user is set.
        username, _ = get_current_user()

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        # Takes back access, or an invitation not yet answered.
        app.db["pets"].update_one(
            {"_id": ObjectId(pet_id)},
            {
                "$pull": {"shared_with": share_username, "share_invites": share_username},
                "$set": {"updated_at": now_utc()},
            },
        )
        if share_username in pet.get("shared_with", []):
            log_deletion("pet", pet["_id"], pet["_id"], viewers=[share_username])

        logger.info(f"Pet unshared: id={pet_id}, owner={username}, unshared_from={share_username}")
        return get_message("pet_unshared", username=share_username)

    except ValueError as e:
        logger.warning(f"Invalid input data for unsharing pet: id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@pets_bp.route("/api/pets/invites", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=PetInviteListResponse), tags=["pets"])
def list_pet_invites():
    """Pets someone has invited the signed-in user to.

    Name, species and owner, nothing more. A pet its owner has not invited is
    neither in this list nor found by its id, so the invitation is the only way in.
    """
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
    update = {"$pull": {"share_invites": username}, "$set": {"updated_at": now_utc()}}
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
    """Accept an invitation: the pet appears in the user's list.

    The invitation is spent either way, so accepting twice answers like an
    invitation that was never there. Access starts at once, with the same rights
    every member has: the records can be read and added to, the pet cannot be
    deleted or handed on.
    """
    return _answer_invite(pet_id, accept=True)


@pets_bp.route("/api/pets/<pet_id>/invite/decline", methods=["POST"])
@login_required
@api.validate(resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse), tags=["pets"])
def decline_pet_invite(pet_id):
    """Decline an invitation.

    The pet stays with its owner and nothing is deleted. The owner may invite again
    later; declining does not close that.
    """
    return _answer_invite(pet_id, accept=False)


@pets_bp.route("/api/pets/<pet_id>/form-defaults", methods=["PUT"])
@login_required
@api.validate(
    body=Request(PetFormDefaults),
    resp=Response(HTTP_200=PetFormDefaultsResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["pets"],
)
def put_pet_form_defaults(pet_id):
    """What a new record's form starts with for this pet.

    Anyone who can add its records can set it, owner or not: the food in the
    bowl is known to whoever feeds the pet. Replaces the whole set. Type and field names are 1-64 of latin
    letters, digits, ``_`` and ``-``; ``date``, ``time``, ``comment``, ``pet_id``, ``_id``, ``type`` and
    ``username`` cannot be remembered. At most 40 types, 30 fields per type and 300 values in all, a value up
    to 200 characters after trimming; otherwise 422. Read them back from ``form_defaults`` in GET /api/pets/{pet_id}.
    """
    username, _ = get_current_user()
    pet, access_error = get_pet_and_validate(pet_id, username)
    if access_error:
        return access_error[0], access_error[1]
    form_defaults = request.context.body.form_defaults  # type: ignore[attr-defined]
    app.db["pets"].update_one({"_id": pet["_id"]}, {"$set": {"form_defaults": form_defaults, "updated_at": now_utc()}})
    return jsonify({"form_defaults": form_defaults})


def _look_conflict(pet: dict):
    """409 with the look as it is now, so the client can show it and let the person choose (as the visit note does)."""
    response, status = error_response("conflict", "Оформление изменили в другом месте, пока вы его правили")
    body = response.get_json()
    body["look"] = pet.get("look") or {}
    return jsonify(body), status


@pets_bp.route("/api/pets/<pet_id>/look", methods=["PUT"])
@login_required
@api.validate(
    body=Request(PetLook),
    resp=Response(
        HTTP_200=PetLookResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_409=ErrorResponse,
        HTTP_422=ErrorResponse,
    ),
    tags=["pets"],
)
def put_pet_look(pet_id):
    """The pet's look: the line, the colour, the name's face, the photo's frame, the backdrop, the scene and the crops.

    Anyone the pet is shared with can set it: the look lives on the pet, so the owner and the family see the same
    thing after a save. Someone without access gets 404. The body replaces the whole look: a part left out or empty
    is dropped, and with every part empty the look is removed. Unknown values answer 422 (the allowed ones are in the schema).

    The look carries a version, like the visit note: a save made from an older copy (``base_version`` is not the stored
    one) answers 409 with the look as it is now, and two saves in the same instant do not both win.
    """
    username, _ = get_current_user()
    pet, access_error = get_pet_and_validate(pet_id, username)
    if access_error:
        return access_error[0], access_error[1]
    body = request.context.body  # type: ignore[attr-defined]
    # "" is a copy of a look that was never saved or was saved before versions existed.
    stored_version = (pet.get("look") or {}).get("version")
    if body.base_version is not None and body.base_version != (stored_version or ""):
        return _look_conflict(pet)
    look = {
        key: value
        for key, value in (
            ("tagline", body.tagline),
            ("accent", body.accent),
            ("font", body.font),
            ("frame", body.frame),
            ("backdrop", body.backdrop),
            ("scene", body.scene),
        )
        if value
    }
    if body.crops:
        look["crops"] = body.crops
    # Taken only if nobody saved between the read above and now.
    guard = {"_id": pet["_id"], "look.version": stored_version} if stored_version is not None else {"_id": pet["_id"]}
    if look:
        look["version"] = uuid.uuid4().hex
        update = {"$set": {"look": look, "updated_at": now_utc()}}
    else:
        update = {"$unset": {"look": ""}, "$set": {"updated_at": now_utc()}}
    result = app.db["pets"].update_one(guard, update)
    if stored_version is not None and result.matched_count == 0:
        return _look_conflict(app.db["pets"].find_one({"_id": pet["_id"]}) or pet)
    return jsonify({"look": look})


@pets_bp.route("/api/pets/<pet_id>/leave", methods=["POST"])
@login_required
@api.validate(resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse), tags=["pets"])
def leave_pet(pet_id):
    """Stop seeing a pet someone shared: only its owner could end a share before.

    Nothing is deleted. The pet, its records and its files stay with the owner; only
    this person's access goes. A pet the caller owns cannot be left, and asking about
    a pet they were never shared with answers the same way.
    """
    username = request.current_user
    try:
        pet_oid = ObjectId(pet_id)
    except Exception:
        return error_response("share_not_member")
    result = app.db["pets"].update_one(
        {"_id": pet_oid, "shared_with": username},
        {"$pull": {"shared_with": username}, "$set": {"updated_at": now_utc()}},
    )
    if result.matched_count == 0:
        return error_response("share_not_member")
    log_deletion("pet", pet_oid, pet_oid, viewers=[username])
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
        HTTP_503=ErrorResponse,
    ),
    tags=["pets"],
)
def delete_pet(pet_id):
    """Delete pet and all related records (cascading delete).

    The owner only, and there is no undo. Everything the pet accumulated goes with
    it: every record, every medication course with its intakes, every document and
    the file behind it, the medical card and any links to it.
    ``GET /api/pets/{pet_id}/deletion-impact`` counts all of that beforehand, and
    the app asks before calling this. If a record cannot be deleted, the pet stays
    and the answer is ``pet_delete_failed``: calling this again finishes the job.
    """
    try:
        # @login_required already guarantees request.current_user is set.
        username, _ = get_current_user()

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]
        return _delete_pet(pet, username)

    except ValueError as e:
        logger.warning(f"Invalid pet_id for deletion: id={pet_id}, user={username}, error={e}")
        return error_response("invalid_pet_id")


@pets_bp.route("/api/pets/local/<local_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
        HTTP_503=ErrorResponse,
    ),
    tags=["pets"],
)
@require_local_record_access("pets", "pet", owner_only=True, tell_deleted=False)
def delete_pet_by_local_id(local_id):
    """Delete a pet by the ``local_id`` the device gave it, for when the device has not got the pet's id.

    The same cascading delete as by id, for the owner. An unknown name, a deleted pet and someone else's pet answer 404 ``record_not_found``.
    """
    return _delete_pet(g.record, g.username)


def _delete_pet(pet: dict, username: str):
    """The delete of one pet found by the access check, by its id or by the local_id the device named."""
    pet_id = str(pet["_id"])
    try:
        purged = purge_pet(pet)
    except PetDeletionFailed:
        # The pet is still there, and calling this again finishes what is left.
        return error_response("pet_delete_failed")
    if not purged:
        return error_response("pet_not_found")

    logger.info(f"Pet deleted: id={pet_id}, user={username}")
    return get_message("pet_deleted")


@pets_bp.route("/api/pets/<pet_id>/deletion-impact", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=PetDeletionImpactResponse, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse), tags=["pets"]
)
def pet_deletion_impact(pet_id):
    """What deleting the pet would take with it: the numbers the confirmation names.

    Records, medication courses, documents and medical card entries, counted and
    nothing else. The owner only, the same people who may delete the pet.
    """
    try:
        username, _ = get_current_user()
        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]
        query = {"pet_id": str(pet["_id"])}
        return jsonify(
            {
                "events": app.db["events"].count_documents({**query, **LIVE_EVENT_FILTER}),
                "medications": app.db["medications"].count_documents(query),
                "documents": app.db["documents"].count_documents(query),
                "medical_records": app.db["medical_records"].count_documents(query),
            }
        )
    except ValueError:
        return error_response("invalid_pet_id")


def purge_pet(pet: dict) -> bool:
    """Remove a pet with everything recorded for it and every file it has.

    Shared by deleting one pet and deleting the owner's account. False if
    the pet was already gone. Raises PetDeletionFailed when a collection could
    not be cleared: the pet is then still there, and the same call can be repeated.
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
        ("medical_records", {"pet_id": pet_id}),
        ("medical_shares", {"pet_id": pet_id}),
        # Scan slots still uploading: they belong to the pet, so they go with it.
        ("document_uploads", {"pet_id": pet_id}),
    ]

    # Captured before the record goes
    old_photo_id = pet.get("photo_file_id")

    # Who could see the pet, read before it goes: they are the ones the deletion is for.
    viewers = pet_viewers(pet_id_obj)
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
        # Fallback for standalone MongoDB (no replica set) or mongomock. Without a
        # transaction the order is the only guarantee: everything the pet owns goes
        # first and the pet document last. Until that last delete the pet is still
        # there, so a failure leaves a DELETE that can be repeated (every delete here
        # is idempotent). The first failure stops the purge.
        error_msg = str(tx_error).lower()
        if "transaction" in error_msg or "replica" in error_msg or "session" in error_msg or "mongomock" in error_msg:
            logger.warning(f"Transactions not supported, using fallback cascading delete: {tx_error}")

            total_deleted = 0
            for collection_name, query in collections_to_clean:
                try:
                    result = app.db[collection_name].delete_many(query)
                except Exception as col_error:
                    logger.error(f"Pet deletion stopped at {collection_name}: id={pet_id}, error={col_error}")
                    raise PetDeletionFailed(collection_name) from col_error
                if result.deleted_count > 0:
                    logger.info(f"Deleted {result.deleted_count} records from {collection_name} for pet {pet_id}")
                    total_deleted += result.deleted_count

            try:
                result = app.db["pets"].delete_one({"_id": pet_id_obj})
            except Exception as pet_error:
                logger.error(f"Pet deletion stopped at the pet itself: id={pet_id}, error={pet_error}")
                raise PetDeletionFailed("pets") from pet_error
            if result.deleted_count == 0:
                return False

            logger.info(f"Pet deleted (fallback): id={pet_id}, total_related_records={total_deleted}")
        else:
            # Re-raise if it's not a transaction-related error
            raise

    log_deletion("pet", pet_id_obj, pet_id_obj, viewers=viewers, local_id=pet.get("local_id"))
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

    # Anything else left under the pet's prefix (thumbnails, an object whose
    # record write failed).
    if storage.storage_configured():
        try:
            storage.delete_prefix(storage.pet_prefix(app.db, pet["owner"], pet_id))
        except Exception as prefix_error:
            logger.warning(f"Failed to clear stored files for pet {pet_id}: {prefix_error}")

    return True


@pets_bp.route("/api/pets/<pet_id>/photo", methods=["GET"])
@picture_route("pet-photo", login_required)
@api.validate(
    query=PhotoQueryParams,
    resp=Response(
        HTTP_200=None, HTTP_422=ErrorResponse, HTTP_401=ErrorResponse, HTTP_404=ErrorResponse, HTTP_500=ErrorResponse
    ),
    tags=["pets"],
)
def get_pet_photo(pet_id):
    """Get pet photo file with optional resizing.

    Readable by everyone the pet is shared with. ``?w=`` and ``?h=`` give a smaller
    copy for a list that has no reason to pull the original: they are rounded up to the nearest standard size,
    and above 1440 px the original goes out. Without them the stored photo goes out as it is: a WebP, or JPEG,
    PNG or GIF for photos stored before the conversion, and any other stored type as
    ``application/octet-stream`` with ``Content-Disposition: attachment``. The answer carries an ETag; a matching
    ``If-None-Match`` gets an empty 304. A pet without a photo answers 404 ``photo_not_found``.
    """
    try:
        # @login_required already guarantees request.current_user is set.
        username = request.current_user

        pet = app.db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return error_response("pet_not_found")

        if pet.get("owner") != username and username not in pet.get("shared_with", []):
            return error_response("pet_not_found")

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
