"""A retried create is saved once: a POST that carries an ``Idempotency-Key`` gets its first answer again.

A phone that loses the network after the server saved a record does not know whether it was saved, and sends the same
request again. With the key, the second request is answered with the first answer and no second record is made. A key
belongs to one user and one request path, and is kept for a day. The same key with another body is refused: the key is
being used for two different things.

Only a request that saved something keeps its key (an answer from 2xx). A refusal or a server error releases the key, so
the request can be sent again as it was. A request still running holds the key for a minute (its lease): a second one
with the same key before then gets 409, and after that the key is taken over, so a request that died is not kept.
"""

import hashlib
import re
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import current_app, request
from pymongo.errors import DuplicateKeyError

import web.app as app
from web.errors import error_response

COLLECTION = "idempotency_keys"
KEY_LIFETIME = timedelta(hours=24)
LEASE = timedelta(seconds=60)
_KEY_SHAPE = re.compile(r"^[!-~]{1,128}$")  # printable ASCII, no spaces, at most 128 characters


def _now() -> datetime:
    """Naive UTC, as the database keeps moments."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def idempotent(view):
    """Put this under the route's ``api.validate``: a request the schema refuses never gets a key, and the view runs
    with its body already checked."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        key = request.headers.get("Idempotency-Key")
        if key is None:
            return view(*args, **kwargs)
        if not _KEY_SHAPE.match(key):
            return error_response("idempotency_key_invalid")

        scope = {"username": request.current_user, "path": f"{request.method} {request.path}", "key": key}
        digest = hashlib.sha256(request.get_data(cache=True)).hexdigest()
        held, answer = _hold(scope, digest, _now())
        if answer is not None:
            return answer

        try:
            result = view(*args, **kwargs)
        except BaseException:
            app.db[COLLECTION].delete_one({"_id": held})
            raise
        response = current_app.make_response(result)
        if 200 <= response.status_code < 300:
            app.db[COLLECTION].update_one(
                {"_id": held},
                {
                    "$set": {
                        "state": "done",
                        "status": response.status_code,
                        "body": response.get_data(as_text=True),
                        "mimetype": response.mimetype,
                    }
                },
            )
        else:
            app.db[COLLECTION].delete_one({"_id": held})
        return response

    return wrapper


def _hold(scope: dict, digest: str, now: datetime):
    """Take the key for this request: ``(row id, None)``, or ``(None, the answer to send instead)``."""
    rows = app.db[COLLECTION]
    try:
        held = rows.insert_one(
            {
                **scope,
                "digest": digest,
                "state": "running",
                "lease_until": now + LEASE,
                "expires_at": now + KEY_LIFETIME,
            }
        ).inserted_id
        return held, None
    except DuplicateKeyError:
        pass

    row = rows.find_one(scope)
    if row is None:
        # Released a moment ago by the request that held it: the client asks again, as it would for a busy key.
        return None, error_response("idempotency_in_progress")
    if row["digest"] != digest:
        return None, error_response("idempotency_key_reused")
    if row["state"] == "done":
        return None, current_app.response_class(row["body"], status=row["status"], mimetype=row["mimetype"])
    if row["lease_until"] > now:
        return None, error_response("idempotency_in_progress")
    taken = rows.update_one(
        {"_id": row["_id"], "state": "running", "lease_until": {"$lte": now}},
        {"$set": {"lease_until": now + LEASE}},
    )
    if taken.modified_count != 1:
        return None, error_response("idempotency_in_progress")
    return row["_id"], None
