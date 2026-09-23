"""Pet document attachments — vaccination certificates, lab results,
insurance papers, photos for the vet, etc. One record = one file.

Storage mirrors the pet-photo path in ``web/pets.py``: images go through
``optimize_image`` (WebP, resized) before landing in GridFS; everything
else (PDF) is stored byte-for-byte with its original content type.
"""

from datetime import datetime, timezone
from io import BytesIO

from bson import ObjectId
from flask import Blueprint, g, jsonify, make_response, request
from flask_pydantic_spec import Request, Response
from PIL import Image

import web.app as app  # to access patched app.db/app.fs in tests
from web.app import api
from web.decorators import require_pet_access, require_record_access
from web.errors import error_response
from web.helpers import apply_pagination, optimize_image, validate_pet_access
from web.messages import get_message
from web.pydantic_helpers import validate_request_data
from web.schemas import (
    DocumentCreate,
    DocumentDetailResponse,
    DocumentListQuery,
    DocumentListResponse,
    DocumentUpdate,
    ErrorResponse,
    PhotoQueryParams,
    SuccessResponse,
)
from web.security import login_required

documents_bp = Blueprint("documents", __name__)

# Images get the same WebP treatment as pet photos; PDF is stored as-is.
# Anything else is rejected — extend this set if a new type is needed.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/pdf",
}
MAX_DOCUMENT_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


def _serialize_document(doc: dict) -> dict:
    """Convert an internal Mongo document doc into the JSON-friendly shape."""
    doc["_id"] = str(doc["_id"])
    doc["pet_id"] = str(doc.get("pet_id", ""))
    doc["file_id"] = str(doc.get("file_id", ""))
    if isinstance(doc.get("created_at"), datetime):
        doc["created_at"] = doc["created_at"].strftime("%Y-%m-%d %H:%M")
    return doc


@documents_bp.route("/api/documents", methods=["POST"])
@login_required
@api.validate(
    body=Request(DocumentCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["documents"],
)
def create_document():
    """Attach a new document (image or PDF) to a pet.

    Request must be ``multipart/form-data`` with the ``DocumentCreate``
    fields (``pet_id``, ``category``, ``title``, optional ``note``) as
    form fields and the file itself under the ``file`` field — unlike
    pet creation, the file is mandatory here, not optional.
    """
    try:
        # @api.validate(body=Request(DocumentCreate)) already parsed and
        # validated the form fields (aborting with its own error response
        # if they were invalid), so this call only re-parses to get the
        # model back — same two-step dance pets.create_pet's identical
        # multipart route uses, rather than relying on the private
        # request.context.body attribute directly.
        data, _ = validate_request_data(request, DocumentCreate, context="document creation")

        username = request.current_user

        # Not @require_pet_access: that decorator reads pet_id from
        # request.context.query/body before this route body runs, and
        # pet creation's own multipart route (create_pet) avoids it for
        # the same reason — do the check explicitly instead.
        success, access_error = validate_pet_access(data.pet_id, username)
        if not success:
            return access_error

        if "file" not in request.files or not request.files["file"].filename:
            return error_response("document_file_required")

        file_storage = request.files["file"]
        content_type = file_storage.content_type or "application/octet-stream"
        if content_type not in ALLOWED_CONTENT_TYPES:
            return error_response("document_unsupported_type")

        raw_bytes = file_storage.read()
        if len(raw_bytes) > MAX_DOCUMENT_SIZE_BYTES:
            return error_response("document_file_too_large")
        file_storage.seek(0)

        original_filename = file_storage.filename

        if content_type.startswith("image/"):
            optimized_result = optimize_image(file_storage)
            if optimized_result:
                optimized_file, stored_content_type = optimized_result
                stored_bytes = optimized_file.getvalue()
                filename_stem = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename
                stored_filename = f"{filename_stem}.webp"
            else:
                stored_bytes = raw_bytes
                stored_content_type = content_type
                stored_filename = original_filename
        else:
            stored_bytes = raw_bytes
            stored_content_type = content_type
            stored_filename = original_filename

        file_id = app.fs.put(BytesIO(stored_bytes), filename=stored_filename, content_type=stored_content_type)

        document_data = {
            "pet_id": data.pet_id,
            "username": username,
            "category": data.category,
            "title": data.title,
            "note": data.note or "",
            "expires_at": data.expires_at,
            "file_id": str(file_id),
            "original_filename": original_filename,
            "content_type": stored_content_type,
            "file_size": len(stored_bytes),
            "created_at": datetime.now(timezone.utc),
        }
        result = app.db.documents.insert_one(document_data)
        app.logger.info(f"Document created: id={result.inserted_id}, pet_id={data.pet_id}, user={username}")
        return get_message("document_created", status=201, id=str(result.inserted_id))
    except Exception as e:
        app.logger.error(f"Error creating document: {e}")
        return error_response("internal_error")


@documents_bp.route("/api/documents", methods=["GET"])
@api.validate(
    query=DocumentListQuery,
    resp=Response(HTTP_200=DocumentListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["documents"],
)
@require_pet_access
def get_documents():
    """List documents for a pet, optionally filtered by category."""
    try:
        query_params = request.context.query  # type: ignore[attr-defined]
        pet_id = g.pet_id
        page = query_params.page
        page_size = query_params.page_size

        mongo_query: dict = {"pet_id": pet_id}
        if query_params.category:
            mongo_query["category"] = query_params.category

        total = app.db.documents.count_documents(mongo_query)
        base_query = app.db.documents.find(mongo_query).sort("created_at", -1)
        paginated_query, _ = apply_pagination(base_query, page, page_size)
        documents = [_serialize_document(d) for d in paginated_query]

        return jsonify({"documents": documents, "page": page, "page_size": page_size, "total": total})
    except Exception as e:
        app.logger.error(f"Error listing documents: {e}")
        return error_response("internal_error")


@documents_bp.route("/api/documents/<id>", methods=["GET"])
@api.validate(
    resp=Response(HTTP_200=DocumentDetailResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["documents"],
)
@require_record_access("documents")
def get_document(id):
    """Fetch a single document's metadata by id."""
    try:
        return jsonify({"document": _serialize_document(g.record)})
    except Exception as e:
        app.logger.error(f"Error fetching document: {e}")
        return error_response("internal_error")


@documents_bp.route("/api/documents/<id>", methods=["PUT"])
@api.validate(
    body=Request(DocumentUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["documents"],
)
@require_record_access("documents")
def update_document(id):
    """Update a document's metadata (category/title/note).

    The file itself is immutable in v1 — delete and re-upload to replace it.
    """
    try:
        document = g.record
        data = request.context.body  # type: ignore[attr-defined]
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}

        if not update_data:
            return error_response("validation_error_no_update_data")

        app.db.documents.update_one({"_id": document["_id"]}, {"$set": update_data})
        return get_message("document_updated")
    except Exception as e:
        app.logger.error(f"Error updating document: {e}")
        return error_response("internal_error")


@documents_bp.route("/api/documents/<id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["documents"],
)
@require_record_access("documents")
def delete_document(id):
    """Delete a document and its underlying file."""
    try:
        document = g.record
        app.db.documents.delete_one({"_id": document["_id"]})
        try:
            app.fs.delete(ObjectId(document["file_id"]))
        except Exception as file_error:
            app.logger.warning(f"Failed to delete document file: file_id={document['file_id']}, error={file_error}")
        return get_message("document_deleted")
    except Exception as e:
        app.logger.error(f"Error deleting document: {e}")
        return error_response("internal_error")


@documents_bp.route("/api/documents/<id>/file", methods=["GET"])
@api.validate(
    query=PhotoQueryParams,
    resp=Response(HTTP_200=None, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse),
    tags=["documents"],
)
@require_record_access("documents")
def get_document_file(id):
    """Serve the document's underlying file bytes.

    Images support the same optional ``?w=&h=`` thumbnail resize as pet
    photos (``pets.get_pet_photo``); PDF and anything else is streamed
    unchanged.
    """
    document = g.record
    try:
        grid_file = app.fs.get(ObjectId(document["file_id"]))
        data = grid_file.read()
        content_type = document.get("content_type") or "application/octet-stream"

        width = request.args.get("w", type=int)
        height = request.args.get("h", type=int)
        if (width or height) and content_type.startswith("image/"):
            try:
                img = Image.open(BytesIO(data))
                if width and not height:
                    height = int(img.height * (width / img.width))
                elif height and not width:
                    width = int(img.width * (height / img.height))
                if width and height:
                    img.thumbnail((width, height), Image.Resampling.LANCZOS)
                    output = BytesIO()
                    img.save(output, format="WEBP", quality=85, method=6)
                    data = output.getvalue()
                    content_type = "image/webp"
            except Exception as resize_err:
                app.logger.warning(f"Document thumbnail resize failed: {resize_err}")

        is_inline = content_type.startswith("image/") or content_type == "application/pdf"
        disposition = "inline" if is_inline else "attachment"

        response = make_response(data)
        response.headers.set("Content-Type", content_type)
        response.headers.set("Content-Disposition", f'{disposition}; filename="{document["original_filename"]}"')
        response.headers.set("Cache-Control", "public, max-age=31536000, immutable")
        response.headers.set("ETag", f'"{document["file_id"]}_{width}_{height}"')
        return response
    except Exception as e:
        app.logger.error(f"Error retrieving document file: id={id}, error={e}", exc_info=True)
        return error_response("upload_error")
