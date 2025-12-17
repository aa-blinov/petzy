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
    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

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
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_401=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["pets"],
)
def create_pet():
    """Create a new pet."""
    try:
        username = getattr(request, "current_user", None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401

        # Manual validation instead of @api.validate(body=...) to support multipart/form-data
        if request.content_type and "multipart/form-data" in request.content_type:
            try:
                # Validate form data using Pydantic
                data_dict = request.form.to_dict()
                data = PetCreate.model_validate(data_dict)
            except Exception as e:
                # Extract the first error message from Pydantic
                error_msg = "Invalid input data"
                if hasattr(e, "errors") and callable(e.errors):
                    errors = e.errors()
                    if errors:
                        error_msg = f"{errors[0]['loc'][0]}: {errors[0]['msg']}"
                return jsonify({"error": error_msg}), 422

            name = data.name
            photo_file_id = None
            if "photo_file" in request.files:
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
                "name": name,
                "breed": data.breed or "",
                "birth_date": birth_date,
                "gender": data.gender or "",
                "photo_file_id": photo_file_id,
                "owner": username,
                "shared_with": [],
                "created_at": datetime.now(timezone.utc),
                "created_by": username,
            }
        else:
            # JSON request
            try:
                data = PetCreate.model_validate(request.get_json())
            except Exception:
                return jsonify({"error": "Invalid input data"}), 422

            name = data.name
            birth_date = parse_date(data.birth_date, allow_future=False)

            pet_data = {
                "name": name,
                "breed": data.breed or "",
                "birth_date": birth_date,
                "gender": data.gender or "",
                "photo_url": data.photo_url or "",
                "owner": username,
                "shared_with": [],
                "created_at": datetime.now(timezone.utc),
                "created_by": username,
            }

        result = app.db["pets"].insert_one(pet_data)
        pet_data["_id"] = str(result.inserted_id)
        if isinstance(pet_data.get("birth_date"), datetime):
            pet_data["birth_date"] = pet_data["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet_data.get("created_at"), datetime):
            pet_data["created_at"] = pet_data["created_at"].strftime("%Y-%m-%d %H:%M")

        logger.info(f"Pet created: id={pet_data['_id']}, name={pet_data['name']}, owner={username}")
        return jsonify({"success": True, "pet": pet_data, "message": "Питомец создан"}), 201

    except ValueError as e:
        logger.warning(f"Invalid input data for pet creation: user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        pet, error_response = get_pet_and_validate(pet_id, username, require_owner=False)
        if error_response:
            return error_response[0], error_response[1]

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
        return jsonify({"error": "Invalid input data"}), 422


@pets_bp.route("/api/pets/<pet_id>", methods=["PUT"])
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
def update_pet(pet_id):
    """Update pet information."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        pet, error_response = get_pet_and_validate(pet_id, username, require_owner=True)
        if error_response:
            return error_response[0], error_response[1]

        # Manual validation to support multipart/form-data
        if request.content_type and "multipart/form-data" in request.content_type:
            try:
                # Validate form data using Pydantic
                data_dict = request.form.to_dict()
                data = PetUpdate.model_validate(data_dict)
            except Exception:
                return jsonify({"error": "Invalid input data"}), 422

            photo_file_id = pet.get("photo_file_id")

            if "photo_file" in request.files:
                photo_file = request.files["photo_file"]

                if photo_file.filename:
                    old_photo_id = pet.get("photo_file_id")
                    if old_photo_id:
                        try:
                            app.fs.delete(ObjectId(old_photo_id))
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete old photo: photo_id={old_photo_id}, pet_id={pet_id}, error={e}"
                            )

                    photo_file_id = str(
                        app.fs.put(
                            photo_file,
                            filename=photo_file.filename,
                            content_type=photo_file.content_type,
                        )
                    )
                elif request.form.get("remove_photo") == "true":
                    old_photo_id = pet.get("photo_file_id")
                    if old_photo_id:
                        try:
                            app.fs.delete(ObjectId(old_photo_id))
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete photo: photo_id={old_photo_id}, pet_id={pet_id}, error={e}"
                            )
                    photo_file_id = None

            birth_date = parse_date(data.birth_date, allow_future=False)

            update_data = {}
            if data.name:
                update_data["name"] = data.name.strip()
            if data.breed is not None:
                update_data["breed"] = data.breed.strip()
            if birth_date is not None:
                update_data["birth_date"] = birth_date
            if data.gender is not None:
                update_data["gender"] = data.gender.strip()
            if photo_file_id is not None:
                update_data["photo_file_id"] = photo_file_id
            elif "photo_file_id" in request.form and request.form.get("photo_file_id") == "":
                update_data["photo_file_id"] = None
        else:
            # JSON request
            try:
                data = PetUpdate.model_validate(request.get_json())
            except Exception:
                return jsonify({"error": "Invalid input data"}), 422

            birth_date = parse_date(data.birth_date, allow_future=False)

            update_data = {}
            if data.name is not None:
                update_data["name"] = data.name
            if data.breed is not None:
                update_data["breed"] = data.breed
            if birth_date is not None:
                update_data["birth_date"] = birth_date
            if data.gender is not None:
                update_data["gender"] = data.gender
            if data.photo_url is not None:
                update_data["photo_url"] = data.photo_url

        if not update_data:
            return jsonify({"error": "Нет данных для обновления"}), 422

        app.db["pets"].update_one({"_id": ObjectId(pet_id)}, {"$set": update_data})
        logger.info(f"Pet updated: id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Данные питомца обновлены"})

    except ValueError as e:
        logger.warning(f"Invalid input data for pet update: id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        pet, error_response = get_pet_and_validate(pet_id, username, require_owner=True)
        if error_response:
            return error_response[0], error_response[1]

        data = request.context.body
        share_username = data.username.strip()

        if not share_username:
            return jsonify({"error": "Имя пользователя обязательно"}), 422

        user = app.db["users"].find_one({"username": share_username, "is_active": True})
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404

        if share_username == username:
            return jsonify({"error": "Нельзя поделиться с самим собой"}), 422

        shared_with = pet.get("shared_with", [])
        if share_username in shared_with:
            return jsonify({"error": "Доступ уже предоставлен этому пользователю"}), 422

        app.db["pets"].update_one({"_id": ObjectId(pet_id)}, {"$addToSet": {"shared_with": share_username}})

        logger.info(f"Pet shared: id={pet_id}, owner={username}, shared_with={share_username}")
        return jsonify({"success": True, "message": f"Доступ предоставлен пользователю {share_username}"}), 200

    except ValueError as e:
        logger.warning(f"Invalid input data for sharing pet: id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


@pets_bp.route("/api/pets/<pet_id>/share/<share_username>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["pets"],
)
def unshare_pet(pet_id, share_username):
    """Remove access from user (owner only)."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        pet, error_response = get_pet_and_validate(pet_id, username, require_owner=True)
        if error_response:
            return error_response[0], error_response[1]

        app.db["pets"].update_one({"_id": ObjectId(pet_id)}, {"$pull": {"shared_with": share_username}})

        logger.info(f"Pet unshared: id={pet_id}, owner={username}, unshared_from={share_username}")
        return jsonify({"success": True, "message": f"Доступ убран у пользователя {share_username}"}), 200

    except ValueError as e:
        logger.warning(f"Invalid input data for unsharing pet: id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        pet, error_response = get_pet_and_validate(pet_id, username, require_owner=True)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["pets"].delete_one({"_id": ObjectId(pet_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Животное не найдено"}), 404

        logger.info(f"Pet deleted: id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Питомец удален"}), 200

    except ValueError as e:
        logger.warning(f"Invalid pet_id for deletion: id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid pet_id format"}), 422


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
            return jsonify({"error": "Unauthorized"}), 401

        pet = app.db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404

        if pet.get("owner") != username and username not in pet.get("shared_with", []):
            return jsonify({"error": "Нет доступа"}), 403

        photo_file_id = pet.get("photo_file_id")
        if not photo_file_id:
            return jsonify({"error": "Фото не найдено"}), 404

        try:
            photo_file = app.fs.get(ObjectId(photo_file_id))
            photo_data = photo_file.read()

            response = make_response(photo_data)
            response.headers.set("Content-Type", photo_file.content_type)
            response.headers.set("Content-Disposition", "inline")
            response.headers.set("Cache-Control", "public, max-age=3600, must-revalidate")
            response.headers.set("ETag", f'"{photo_file_id}"')
            logger.info(f"Pet photo retrieved: pet_id={pet_id}, user={username}")
            return response
        except Exception as e:
            logger.error(f"Error retrieving pet photo: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
            return jsonify({"error": "Ошибка загрузки фото"}), 404

    except (InvalidId, TypeError, ValueError) as e:
        logger.warning(
            f"Invalid pet_id for photo: id={pet_id}, user={getattr(request, 'current_user', None)}, error={e}"
        )
        return jsonify({"error": "Неверный формат pet_id"}), 422
