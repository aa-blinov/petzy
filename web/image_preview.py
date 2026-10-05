"""A picture the browser cannot draw, made drawable.

A phone's HEIC photo is shown by Safari and by nothing else: in Chrome the thumbnail of a picked file is a broken image
and the crop window of a pet's photo is empty. The file is sent here, comes back as a WebP of a size to look at, and is
what the form shows. Nothing is stored: the form sends the original when the person saves, and the server converts it then.
"""

from flask import Blueprint, make_response, request

from web.app import limiter
from web.documents import ALLOWED_CONTENT_TYPES, MAX_DOCUMENT_SIZE_BYTES, _starts_like
from web.errors import error_response
from web.helpers import optimize_image
from web.security import login_required

image_preview_bp = Blueprint("image_preview", __name__)

PREVIEW_SIDE = 1600  # px: enough to crop from and to look at on a phone


@image_preview_bp.route("/api/images/preview", methods=["POST"])
@login_required
@limiter.limit("120 per hour")
def preview_image():
    """The picture in ``file`` as WebP (``image/webp``), not stored."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return error_response("document_file_required")
    content_type = upload.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES or content_type == "application/pdf":
        return error_response("document_unsupported_type")
    raw = upload.read()
    if len(raw) > MAX_DOCUMENT_SIZE_BYTES:
        return error_response("document_file_too_large")
    if not _starts_like(raw[:16], content_type):
        return error_response("document_content_mismatch")
    upload.seek(0)
    converted = optimize_image(upload, max_width=PREVIEW_SIDE, max_height=PREVIEW_SIDE)
    if not converted:
        return error_response("document_content_mismatch")
    data = converted[0].getvalue()
    response = make_response(data)
    response.headers["Content-Type"] = "image/webp"
    response.headers["Cache-Control"] = "no-store"
    return response
