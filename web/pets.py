"""Pets management routes (API)."""

from datetime import datetime, timezone
from io import BytesIO

from PIL import Image
from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, make_response, request, url_for
from flask_pydantic_spec import Request, Response

from web.app import api, logger  # shared logger and api
from web.security import login_required, get_current_user
import web.app as app  # to access patched app.db/app.fs in tests
from web.helpers import get_pet_and_validate, parse_date, optimize_image
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

# Default tiles settings (alphabetical order in Russian)
DEFAULT_TILES_SETTINGS = {
    "order": [
        "weight",        # Вес
        "defecation",    # Дефекация
        "feeding",       # Дневная порция корма
        "eye_drops",     # Закапывание глаз
        "asthma",        # Приступ астмы
        "litter",        # Смена лотка
        "ear_cleaning",  # Чистка ушей
        "tooth_brushing" # Чистка зубов
    ],
    "visible": {
        "weight": True,
        "defecation": True,
        "feeding": True,
        "eye_drops": True,
        "asthma": True,
        "litter": True,
        "ear_cleaning": True,
        "tooth_brushing": True,
    }
}


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
    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    pets = list(app.db["pets"].find({"$or": [{"owner": username}, {"shared_with": username}]}).sort("created_at", -1))

    processed_pets = []
    for pet in pets:
        # Convert all ObjectId instances to strings recursively
        pet = convert_objectid_to_str(pet)
        
        # Ensure _id is string (already converted by convert_objectid_to_str, but double-check)
        pet["_id"] = str(pet["_id"])
        
        # Convert photo_file_id to string if it exists
        if pet.get("photo_file_id"):
            pet["photo_file_id"] = str(pet["photo_file_id"])
            # Add cache-busting parameter using photo_file_id so browser gets new image when it changes
            pet["photo_url"] = url_for("pets.get_pet_photo", pet_id=pet["_id"], _external=False) + f"?v={pet['photo_file_id'][:8]}"
        
        if isinstance(pet.get("birth_date"), datetime):
            pet["birth_date"] = pet["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet.get("created_at"), datetime):
            pet["created_at"] = pet["created_at"].strftime("%Y-%m-%d %H:%M")

        pet["current_user_is_owner"] = pet.get("owner") == username
        
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
            if validation_error:
                # validation_error is already a (jsonify, status) tuple
                return validation_error[0], validation_error[1]
        else:
            # JSON request - already validated by @api.validate(body=Request(PetCreate))
            data = request.context.body  # type: ignore[attr-defined]

        # Handle photo file upload (only for multipart/form-data)
        photo_file_id = None
        if is_multipart and "photo_file" in request.files:
            photo_file = request.files["photo_file"]
            if photo_file.filename:
                # Optimize image to WebP format
                optimized_result = optimize_image(photo_file)
                if optimized_result:
                    optimized_file, content_type = optimized_result
                    # Generate filename with .webp extension
                    original_filename = photo_file.filename
                    filename_without_ext = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename
                    optimized_filename = f"{filename_without_ext}.webp"
                    
                    photo_file_id = str(
                        app.fs.put(
                            optimized_file,
                            filename=optimized_filename,
                            content_type=content_type,
                        )
                    )
                else:
                    # Fallback to original file if optimization fails
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
            "species": data.species or "",
            "birth_date": birth_date,
            "gender": data.gender or "",
            "is_neutered": data.is_neutered if data.is_neutered is not None else False,
            "health_notes": data.health_notes or "",
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

        logger.info(f"Pet created: id={pet_data['_id']}, name={pet_data['name']}, owner={username}")
        return get_message("pet_created", status=201, pet=pet_data)

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
            pet["photo_url"] = url_for("pets.get_pet_photo", pet_id=pet["_id"], _external=False) + f"?v={pet['photo_file_id'][:8]}"

        pet["current_user_is_owner"] = pet.get("owner") == username
        
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
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        is_multipart = request.content_type and "multipart/form-data" in request.content_type
        if is_multipart:
            data, validation_error = validate_request_data(request, PetUpdate, context="pet update")
            if validation_error:
                # validation_error is already a (jsonify, status) tuple
                return validation_error[0], validation_error[1]
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

                    # Optimize image to WebP format
                    optimized_result = optimize_image(photo_file)
                    if optimized_result:
                        optimized_file, content_type = optimized_result
                        # Generate filename with .webp extension
                        original_filename = photo_file.filename
                        filename_without_ext = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename
                        optimized_filename = f"{filename_without_ext}.webp"
                        
                        photo_file_id = str(
                            app.fs.put(
                                optimized_file,
                                filename=optimized_filename,
                                content_type=content_type,
                            )
                        )
                    else:
                        # Fallback to original file if optimization fails
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
            logger.info(f"Photo handling: photo_file_id={photo_file_id}, remove_photo={request.form.get('remove_photo')}")
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
            # JSON request - handle photo_url
            if data.photo_url is not None:
                update_data["photo_url"] = data.photo_url

        logger.info(f"Update data for pet {pet_id}: {update_data}")

        if not update_data:
            return error_response("validation_error_no_update_data")

        app.db["pets"].update_one({"_id": ObjectId(pet_id)}, {"$set": update_data})
        logger.info(f"Pet updated: id={pet_id}, user={username}")
        return get_message("pet_updated")

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
        return error_response("validation_error", str(e))


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
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        pet, access_error = get_pet_and_validate(pet_id, username, require_owner=True)
        if access_error:
            return access_error[0], access_error[1]

        pet_id_obj = ObjectId(pet_id)
        
        # List of collections with related records to delete
        # Using pet_id as string for most collections
        collections_to_clean = [
            ("asthma_attacks", {"pet_id": pet_id}),
            ("defecations", {"pet_id": pet_id}),
            ("weights", {"pet_id": pet_id}),
            ("feedings", {"pet_id": pet_id}),
            ("litter_changes", {"pet_id": pet_id}),
            ("eye_drops", {"pet_id": pet_id}),
            ("ear_cleaning", {"pet_id": pet_id}),
            ("tooth_brushing", {"pet_id": pet_id}),
            ("medication_intakes", {"pet_id": pet_id}),
            ("medications", {"pet_id": pet_id}),
        ]
        
        # Delete photo from GridFS if exists
        old_photo_id = pet.get("photo_file_id") if pet else None

        # Try to use transaction if available
        try:
            with app.db.client.start_session() as session:
                with session.start_transaction():
                    # Delete all related records
                    total_deleted = 0
                    for collection_name, query in collections_to_clean:
                        result = app.db[collection_name].delete_many(query, session=session)
                        if result.deleted_count > 0:
                            logger.info(
                                f"Deleted {result.deleted_count} records from {collection_name} for pet {pet_id}"
                            )
                            total_deleted += result.deleted_count
                    
                    # Delete the pet itself
                    result = app.db["pets"].delete_one({"_id": pet_id_obj}, session=session)
                    
                    if result.deleted_count == 0:
                        raise Exception("Pet not found during deletion")
                    
                    logger.info(
                        f"Pet deleted with transaction: id={pet_id}, user={username}, "
                        f"total_related_records={total_deleted}"
                    )
        except Exception as tx_error:
            # Fallback for standalone MongoDB (no replica set) or mongomock
            error_msg = str(tx_error).lower()
            if ("transaction" in error_msg or "replica" in error_msg or 
                "session" in error_msg or "mongomock" in error_msg):
                logger.warning(
                    f"Transactions not supported, using fallback cascading delete: {tx_error}"
                )
                
                # Delete pet first, then related records (prevents foreign key issues)
                result = app.db["pets"].delete_one({"_id": pet_id_obj})
                
                if result.deleted_count == 0:
                    return error_response("pet_not_found")
                
                # Best-effort deletion of related records
                total_deleted = 0
                failed_collections = []
                for collection_name, query in collections_to_clean:
                    try:
                        result = app.db[collection_name].delete_many(query)
                        if result.deleted_count > 0:
                            logger.info(
                                f"Deleted {result.deleted_count} records from {collection_name} for pet {pet_id}"
                            )
                            total_deleted += result.deleted_count
                    except Exception as col_error:
                        logger.error(
                            f"Failed to delete from {collection_name} for pet {pet_id}: {col_error}"
                        )
                        failed_collections.append(collection_name)
                
                if failed_collections:
                    logger.warning(
                        f"Some related records may not have been deleted for pet {pet_id}: "
                        f"{', '.join(failed_collections)}"
                    )
                
                logger.info(
                    f"Pet deleted (fallback): id={pet_id}, user={username}, "
                    f"total_related_records={total_deleted}"
                )
            else:
                # Re-raise if it's not a transaction-related error
                raise

        # Delete photo from GridFS (outside transaction as GridFS doesn't support transactions)
        if old_photo_id:
            try:
                app.fs.delete(ObjectId(old_photo_id))
                logger.info(f"Deleted photo {old_photo_id} for pet {pet_id}")
            except Exception as photo_error:
                # Log but don't fail the request
                logger.warning(
                    f"Failed to delete photo {old_photo_id} for pet {pet_id}: {photo_error}"
                )

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
    """Get pet photo file with optional resizing."""
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

        # Get optional width and height for resizing
        width = request.args.get("w", type=int)
        height = request.args.get("h", type=int)

        try:
            photo_file = app.fs.get(ObjectId(photo_file_id))
            photo_data = photo_file.read()
            content_type = photo_file.content_type or "image/jpeg"

            # If resizing requested
            if (width or height) and content_type.startswith("image/"):
                try:
                    img = Image.open(BytesIO(photo_data))
                    
                    # Calculate aspect ratio if only one dimension is provided
                    if width and not height:
                        height = int(img.height * (width / img.width))
                    elif height and not width:
                        width = int(img.width * (height / img.height))
                    
                    if width and height:
                        img.thumbnail((width, height), Image.Resampling.LANCZOS)
                        
                        output = BytesIO()
                        # Use WebP if requested or keep original format (but WebP is better for optimization)
                        format_to_save = "WEBP"
                        img.save(output, format=format_to_save, quality=85, method=6)
                        photo_data = output.getvalue()
                        content_type = "image/webp"
                except Exception as resize_err:
                    logger.warning(f"Resizing failed: {resize_err}")
                    # Fallback to original data if resizing fails

            response = make_response(photo_data)
            response.headers.set("Content-Type", content_type)
            response.headers.set("Content-Disposition", "inline")
            response.headers.set("Cache-Control", "public, max-age=31536000, immutable")
            response.headers.set("ETag", f'"{photo_file_id}_{width}_{height}"')
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
