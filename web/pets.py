"""Pets management routes (API)."""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, make_response, request, url_for
from flask_pydantic_spec import Request, Response

from web.app import api, logger  # shared logger and api
from web.security import login_required, get_current_user
import web.app as app  # to access patched app.db/app.fs in tests
from web.helpers import get_pet_and_validate, parse_date
from web.errors import error_response
from web.messages import get_message
from web.pydantic_helpers import validate_request_data
from web.schemas import (
    PetCreate,
    PetUpdate,
    PetResponseWrapper,
    PetListResponse,
    PetShareRequest,
    SuccessResponse,
    ErrorResponse,
)


pets_bp = Blueprint("pets", __name__)


@pets_bp.route("/api/pets", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=PetListResponse), tags=["pets"])
def get_pets():
    """Get list of all pets accessible to current user."""
    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    pets = list(app.db["pets"].find({"$or": [{"owner": username}, {"shared_with": username}]}).sort("created_at", -1))

    for pet in pets:
        pet["_id"] = str(pet["_id"])
        if isinstance(pet.get("birth_date"), datetime):
            pet["birth_date"] = pet["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet.get("created_at"), datetime):
            pet["created_at"] = pet["created_at"].strftime("%Y-%m-%d %H:%M")

        if pet.get("photo_file_id"):
            pet["photo_url"] = url_for("pets.get_pet_photo", pet_id=pet["_id"], _external=False)

        pet["current_user_is_owner"] = pet.get("owner") == username

    return jsonify({"pets": pets})


@pets_bp.route("/api/pets", methods=["POST"])
@login_required
@api.validate(
    body=Request(PetCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_401=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["pets"],
)
def create_pet():
    """Create a new pet."""
    try:
        username = getattr(request, "current_user", None)
        if not username:
            return error_response("unauthorized")

        # Validate request data (supports both JSON and multipart/form-data)
        # For JSON: use request.context.body (validated by @api.validate)
        # For multipart: use validate_request_data helper
        is_multipart = request.content_type and "multipart/form-data" in request.content_type
        if is_multipart:
            data, validation_error = validate_request_data(request, PetCreate, context="pet creation")
            if validation_error or data is None:
                return validation_error if validation_error else error_response("validation_error")
        else:
            # JSON request - already validated by @api.validate(body=Request(PetCreate))
            data = request.context.body  # type: ignore[attr-defined]

        # Handle photo file upload (only for multipart/form-data)
        photo_file_id = None
        if is_multipart and "photo_file" in request.files:
            photo_file = request.files["photo_file"]
            if photo_file.filename:
                photo_file_id = str(
                    app.fs.put(
                        photo_file,
                        filename=photo_file.filename,
                        content_type=photo_file.content_type,
                    )
                )

        birth_date = parse_date(data.birth_date, allow_future=False)

        pet_data = {
            "name": data.name,
            "breed": data.breed or "",
            "birth_date": birth_date,
            "gender": data.gender or "",
            "owner": username,
            "shared_with": [],
            "created_at": datetime.now(timezone.utc),
            "created_by": username,
        }

        # Add photo_file_id for multipart or photo_url for JSON
        if is_multipart:
            pet_data["photo_file_id"] = photo_file_id
        else:
            pet_data["photo_url"] = data.photo_url or ""

        result = app.db["pets"].insert_one(pet_data)
        pet_data["_id"] = str(result.inserted_id)
        if isinstance(pet_data.get("birth_date"), datetime):
            pet_data["birth_date"] = pet_data["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet_data.get("created_at"), datetime):
            pet_data["created_at"] = pet_data["created_at"].strftime("%Y-%m-%d %H:%M")

        logger.info(f"Pet created: id={pet_data['_id']}, name={pet_data['name']}, owner={username}")
        return get_message("pet_created", status=201, pet=pet_data)

    except ValueError as e:
        logger.warning(f"Invalid input data for pet creation: user={username}, error={e}")
        return error_response("validation_error")


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
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=False)
        if access_error:
            return access_error[0], access_error[1]
        if pet is None:
            # Защита от некорректных/mock-результатов helper'а
            return error_response("pet_not_found")

        pet["_id"] = str(pet["_id"])
        if isinstance(pet.get("birth_date"), datetime):
            pet["birth_date"] = pet["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet.get("created_at"), datetime):
            pet["created_at"] = pet["created_at"].strftime("%Y-%m-%d %H:%M")

        if pet.get("photo_file_id"):
            pet["photo_url"] = url_for("pets.get_pet_photo", pet_id=pet["_id"], _external=False)

        pet["current_user_is_owner"] = pet.get("owner") == username

        return jsonify({"pet": pet})

    except ValueError as e:
        logger.warning(
            f"Invalid input data for get_pet: id={pet_id}, user={getattr(request, 'current_user', None)}, error={e}"
        )
        return error_response("validation_error")


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
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        # Validate request data (supports both JSON and multipart/form-data)
        # For JSON: use request.context.body (validated by @api.validate)
        # For multipart: use validate_request_data helper
        is_multipart = request.content_type and "multipart/form-data" in request.content_type
        if is_multipart:
            data, validation_error = validate_request_data(request, PetUpdate, context="pet update")
            if validation_error or data is None:
                return validation_error if validation_error else error_response("validation_error")
        else:
            # JSON request - already validated by @api.validate(body=Request(PetUpdate))
            data = request.context.body  # type: ignore[attr-defined]

        # Handle photo file upload/removal (only for multipart/form-data)
        photo_file_id = pet.get("photo_file_id") if pet else None
        if is_multipart:
            if "photo_file" in request.files:
                photo_file = request.files["photo_file"]
                if photo_file.filename:
                    # Delete old photo if exists
                    old_photo_id = pet.get("photo_file_id") if pet else None
                    if old_photo_id:
                        try:
                            app.fs.delete(ObjectId(old_photo_id))
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete old photo: photo_id={old_photo_id}, pet_id={pet_id}, error={e}"
                            )

                    # Upload new photo
                    photo_file_id = str(
                        app.fs.put(
                            photo_file,
                            filename=photo_file.filename,
                            content_type=photo_file.content_type,
                        )
                    )
                elif request.form.get("remove_photo") == "true":
                    # Remove photo
                    old_photo_id = pet.get("photo_file_id") if pet else None
                    if old_photo_id:
                        try:
                            app.fs.delete(ObjectId(old_photo_id))
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete photo: photo_id={old_photo_id}, pet_id={pet_id}, error={e}"
                            )
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

        # Handle photo fields based on request type
        if is_multipart:
            if photo_file_id is not None:
                update_data["photo_file_id"] = photo_file_id
            elif "photo_file_id" in request.form and request.form.get("photo_file_id") == "":
                update_data["photo_file_id"] = None
        else:
            # JSON request - handle photo_url
            if data.photo_url is not None:
                update_data["photo_url"] = data.photo_url

        if not update_data:
            return error_response("validation_error_no_update_data")

        app.db["pets"].update_one({"_id": ObjectId(pet_id)}, {"$set": update_data})
        logger.info(f"Pet updated: id={pet_id}, user={username}")
        return get_message("pet_updated")

    except ValueError as e:
        logger.warning(f"Invalid input data for pet update: id={pet_id}, user={username}, error={e}")
        return error_response("validation_error")


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
    """Share pet with another user (owner only)."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

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

        app.db["pets"].update_one({"_id": ObjectId(pet_id)}, {"$addToSet": {"shared_with": share_username}})

        logger.info(f"Pet shared: id={pet_id}, owner={username}, shared_with={share_username}")
        return get_message("pet_shared", username=share_username)

    except ValueError as e:
        logger.warning(f"Invalid input data for sharing pet: id={pet_id}, user={username}, error={e}")
        return error_response("validation_error")


@pets_bp.route("/api/pets/<pet_id>/share/<share_username>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["pets"],
)
def unshare_pet(pet_id, share_username):
    """Remove access from user (owner only)."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        app.db["pets"].update_one({"_id": ObjectId(pet_id)}, {"$pull": {"shared_with": share_username}})

        logger.info(f"Pet unshared: id={pet_id}, owner={username}, unshared_from={share_username}")
        return get_message("pet_unshared", username=share_username)

    except ValueError as e:
        logger.warning(f"Invalid input data for unsharing pet: id={pet_id}, user={username}, error={e}")
        return error_response("validation_error")


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
    """Delete pet."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        result = app.db["pets"].delete_one({"_id": ObjectId(pet_id)})

        if result.deleted_count == 0:
            return error_response("pet_not_found")

        logger.info(f"Pet deleted: id={pet_id}, user={username}")
        return get_message("pet_deleted")

    except ValueError as e:
        logger.warning(f"Invalid pet_id for deletion: id={pet_id}, user={username}, error={e}")
        return error_response("invalid_pet_id")


@pets_bp.route("/api/pets/<pet_id>/photo", methods=["GET"])
@login_required
@api.validate(
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
    """Get pet photo file."""
    try:
        username = getattr(request, "current_user", None)
        if not username:
            return error_response("unauthorized")

        pet = app.db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return error_response("pet_not_found")

        if pet.get("owner") != username and username not in pet.get("shared_with", []):
            return error_response("pet_forbidden")

        photo_file_id = pet.get("photo_file_id")
        if not photo_file_id:
            return error_response("photo_not_found")

        try:
            photo_file = app.fs.get(ObjectId(photo_file_id))
            photo_data = photo_file.read()

            response = make_response(photo_data)
            content_type = photo_file.content_type or "image/jpeg"
            response.headers.set("Content-Type", content_type)
            response.headers.set("Content-Disposition", "inline")
            response.headers.set("Cache-Control", "public, max-age=3600, must-revalidate")
            response.headers.set("ETag", f'"{photo_file_id}"')
            logger.info(f"Pet photo retrieved: pet_id={pet_id}, user={username}")
            return response
        except Exception as e:
            logger.error(f"Error retrieving pet photo: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
            return error_response("upload_error")

    except (InvalidId, TypeError, ValueError) as e:
        logger.warning(
            f"Invalid pet_id for photo: id={pet_id}, user={getattr(request, 'current_user', None)}, error={e}"
        )
        return error_response("invalid_pet_id")
