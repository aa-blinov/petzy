"""Pet document attachments — vaccination certificates, lab results,
insurance papers, photos for the vet, etc. One record = one file.

Storage mirrors the pet-photo path in ``web/pets.py``: images go through
``optimize_image`` (WebP, resized) before landing in GridFS; everything
else (PDF) is stored byte-for-byte with its original content type.
"""

from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from flask import Blueprint, g, jsonify, make_response, redirect, request
from flask_pydantic_spec import Request, Response

import web.app as app  # to access patched app.db/app.fs in tests
from web import storage
from web.app import api
from web.decorators import require_pet_access, require_record_access
from web.errors import error_response
from web.helpers import (
    PRIVATE_IMMUTABLE_CACHE,
    apply_pagination,
    delete_stored_file,
    load_image_variant,
    optimize_image,
    snap_thumbnail_size,
    store_file,
    validate_pet_access,
    validate_pet_access_and_get,
)
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
    ScanUploadComplete,
    ScanUploadRequest,
    ScanUploadSlot,
    StorageStatus,
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
# 10 MB: the host proxy in front of the stack caps request bodies there, so
# anything larger never arrived. Bigger files go in as scans (web/storage.py).
MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024


# Where scan archives go; photos and PDFs of scans can sit there too.
SCAN_CATEGORY = "imaging"


def _serialize_document(doc: dict) -> dict:
    """Convert an internal Mongo document doc into the JSON-friendly shape."""
    doc["_id"] = str(doc["_id"])
    doc["pet_id"] = str(doc.get("pet_id", ""))
    # Where a file sits in the bucket is ours to know, not the client's.
    doc.pop("file_id", None)
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
        pet, access_error = validate_pet_access_and_get(data.pet_id, username)
        if access_error:
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

        ext = "." + stored_filename.rsplit(".", 1)[-1].lower() if "." in stored_filename else ""
        # Under the pet owner's prefix, whoever attaches it.
        file_id = store_file(pet["owner"], data.pet_id, "documents", stored_bytes, stored_content_type, ext)

        document_data = {
            "pet_id": data.pet_id,
            "username": username,
            "category": data.category,
            "title": data.title,
            "note": data.note or "",
            "expires_at": data.expires_at,
            "file_id": file_id,
            "original_filename": original_filename,
            "content_type": stored_content_type,
            "file_size": len(stored_bytes),
            "created_at": datetime.now(timezone.utc),
        }
        result = app.db.documents.insert_one(document_data)
        app.logger.info(f"Document created: id={result.inserted_id}, pet_id={data.pet_id}, user={username}")
        return get_message("document_created", status=201, id=str(result.inserted_id))
    except storage.StorageNotConfigured:
        return error_response("storage_not_configured")
    except Exception as e:
        app.logger.error(f"Error creating document: {e}")
        return error_response("internal_error")


@documents_bp.route("/api/documents/storage", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=StorageStatus), tags=["documents"])
def storage_status():
    """Whether scans (large archives in object storage) can be uploaded."""
    return jsonify({"scans_enabled": storage.storage_configured(), "max_scan_bytes": storage.MAX_SCAN_BYTES})


@documents_bp.route("/api/documents/scans", methods=["POST"])
@login_required
@api.validate(
    body=Request(ScanUploadRequest),
    resp=Response(HTTP_201=ScanUploadSlot, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_503=ErrorResponse),
    tags=["documents"],
)
def create_scan_upload():
    """Reserve a slot and a signed URL to PUT a scan archive to storage.

    The file never passes through this process (see web/storage.py); it is
    checked when the client confirms the upload.
    """
    if not storage.storage_configured():
        return error_response("storage_not_configured")
    data = request.context.body  # type: ignore[attr-defined]
    username = request.current_user

    pet, access_error = validate_pet_access_and_get(data.pet_id, username)
    if access_error:
        return access_error

    fmt = storage.scan_format(data.filename)
    if fmt is None:
        return error_response("scan_unsupported_type")
    if data.size > storage.MAX_SCAN_BYTES:
        return error_response("scan_too_large")
    ext, content_type, family = fmt

    try:
        upload_id = uuid4().hex
        # Under the pet owner's prefix; the real filename is kept in Mongo.
        key = storage.new_key(app.db, pet["owner"], data.pet_id, "scans", ext)
        upload_url = storage.upload_url(key, content_type, data.size)
        app.db.document_uploads.insert_one(
            {
                "_id": upload_id,
                "key": key,
                "pet_id": data.pet_id,
                "username": username,
                "filename": data.filename,
                "size": data.size,
                "content_type": content_type,
                "family": family,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception as e:
        app.logger.error(f"Error creating scan upload slot: {e}")
        return error_response("internal_error")

    return (
        jsonify(
            {
                "upload_id": upload_id,
                "upload_url": upload_url,
                "content_type": content_type,
                "max_bytes": storage.MAX_SCAN_BYTES,
            }
        ),
        201,
    )


@documents_bp.route("/api/documents/scans/<upload_id>/complete", methods=["POST"])
@login_required
@api.validate(
    body=Request(ScanUploadComplete),
    resp=Response(HTTP_201=SuccessResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["documents"],
)
def complete_scan_upload(upload_id):
    """Check the uploaded object and turn it into a document."""
    if not storage.storage_configured():
        return error_response("storage_not_configured")
    data = request.context.body  # type: ignore[attr-defined]
    username = request.current_user

    slot = app.db.document_uploads.find_one({"_id": upload_id, "username": username})
    if not slot:
        return error_response("scan_upload_not_found")
    # Access is checked again: the pet may have been unshared meanwhile.
    success, access_error = validate_pet_access(slot["pet_id"], username)
    if not success:
        return access_error

    def discard():
        try:
            storage.delete_object(slot["key"])
        finally:
            app.db.document_uploads.delete_one({"_id": upload_id})

    try:
        size = storage.object_size(slot["key"])
        if size is None or size != slot["size"]:
            # Not there yet, or cut short: keep the slot so a retried PUT
            # can still be confirmed.
            return error_response("scan_upload_incomplete")
        if size > storage.MAX_SCAN_BYTES:
            discard()
            return error_response("scan_too_large")
        if not storage.matches_family(storage.read_head(slot["key"]), slot["family"]):
            discard()
            return error_response("scan_content_mismatch")

        document_data = {
            "pet_id": slot["pet_id"],
            "username": username,
            "category": SCAN_CATEGORY,
            "title": data.title,
            "note": data.note or "",
            "expires_at": data.expires_at,
            "file_id": slot["key"],
            # Downloaded through a signed redirect, never streamed by us.
            "scan": True,
            "original_filename": slot["filename"],
            "content_type": slot["content_type"],
            "file_size": size,
            "created_at": datetime.now(timezone.utc),
        }
        result = app.db.documents.insert_one(document_data)
        app.db.document_uploads.delete_one({"_id": upload_id})
        app.logger.info(f"Scan document created: id={result.inserted_id}, pet_id={slot['pet_id']}, user={username}")
        return get_message("document_created", status=201, id=str(result.inserted_id))
    except Exception as e:
        app.logger.error(f"Error completing scan upload: {e}")
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
        # A scan archive is downloaded, never previewed: it stays in its
        # own category rather than showing up among photos and PDFs.
        if document.get("scan") and update_data.get("category", SCAN_CATEGORY) != SCAN_CATEGORY:
            return error_response("scan_category_fixed")

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
            delete_stored_file(document["file_id"])
        except Exception as file_error:
            app.logger.warning(f"Failed to delete document file: file_id={document['file_id']}, error={file_error}")
        return get_message("document_deleted")
    except Exception as e:
        app.logger.error(f"Error deleting document: {e}")
        return error_response("internal_error")


_EXTENSION_BY_TYPE = {
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    # Scans keep their own extension: ".tar.gz" vs ".tgz" vs ".gz" all
    # share one content type, so there's no single right one to force.
}


def content_disposition(disposition: str, original_filename: str, content_type: str) -> str:
    """A Content-Disposition value that survives any filename.

    The raw original name went straight into ``filename="…"``: a Cyrillic
    name can't be encoded into a latin-1 header, so the download failed,
    and a ``"`` in the name broke the header. RFC 5987 ``filename*`` carries
    the real UTF-8 name, with a plain-ASCII ``filename`` fallback. The
    extension follows what's actually stored — images are converted to
    WebP, so "photo.jpg" is served as "photo.webp".
    """
    stem, _, ext = original_filename.rpartition(".")
    if not stem:
        stem, ext = original_filename, ""
    ext = _EXTENSION_BY_TYPE.get(content_type, f".{ext}" if ext else "")
    name = f"{stem}{ext}"
    ascii_stem = "".join(c for c in stem if 32 <= ord(c) < 127 and c not in '"\\').strip() or "document"
    return f"{disposition}; filename=\"{ascii_stem}{ext}\"; filename*=UTF-8''{quote(name)}"


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
    if document.get("scan"):
        # Up to 500 MB: hand out a short-lived signed link rather than
        # streaming it through this process.
        if not storage.storage_configured():
            return error_response("storage_not_configured")
        disposition = content_disposition("attachment", document["original_filename"], document["content_type"])
        response = redirect(storage.download_url(document["file_id"], disposition), code=302)
        response.headers.set("Cache-Control", "private, no-store")
        return response

    width = snap_thumbnail_size(request.args.get("w", type=int))
    height = snap_thumbnail_size(request.args.get("h", type=int))
    etag = f"{storage.file_version(document['file_id'])}_{width}_{height}"
    if request.if_none_match.contains(etag):
        response = make_response("", 304)
        response.set_etag(etag)
        response.headers.set("Cache-Control", PRIVATE_IMMUTABLE_CACHE)
        return response

    try:
        data, content_type = load_image_variant(document["file_id"], width, height, document.get("content_type"))

        is_inline = content_type.startswith("image/") or content_type == "application/pdf"
        disposition = "inline" if is_inline else "attachment"

        response = make_response(data)
        response.headers.set("Content-Type", content_type)
        response.headers.set(
            "Content-Disposition", content_disposition(disposition, document["original_filename"], content_type)
        )
        response.headers.set("Cache-Control", PRIVATE_IMMUTABLE_CACHE)
        response.set_etag(etag)
        return response
    except Exception as e:
        app.logger.error(f"Error retrieving document file: id={id}, error={e}", exc_info=True)
        return error_response("upload_error")
