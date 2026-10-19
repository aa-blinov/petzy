from functools import wraps
from flask import request, g

from web.app import limiter
from web.configs import RATE_LIMIT_CONFIG
from web.security import PAT_SCOPE_ATTR, PERSONAL_TOKEN_SCOPES, get_current_user, login_required
from web.helpers import validate_pet_access_and_get, get_record_and_validate_access


def pat_allowed(scope: str):
    """Let a personal access token (``ptz_...``) call this route, if it holds ``scope``.

    Put it directly below ``@login_required``. web/security.py (``check_personal_token``) reads the scope before the
    view runs: a token without it answers 403 ``token_scope_missing``, and a route without this decorator answers 403
    ``token_not_allowed``. The limit (``personal_token_limit``, 120 a minute) is counted per token here, for each
    request that holds one: a session is not limited this way.
    """
    if scope not in PERSONAL_TOKEN_SCOPES:
        raise ValueError(f"unknown personal token scope: {scope}")

    def decorator(view):
        limited = limiter.shared_limit(
            lambda: RATE_LIMIT_CONFIG["personal_token_limit"],
            scope="personal_tokens",
            key_func=lambda: getattr(request, "pat_id", None) or "",
            exempt_when=lambda: not getattr(request, "pat_id", None),
        )(view)
        setattr(limited, PAT_SCOPE_ATTR, scope)
        return limited

    return decorator


def require_pet_access(f):
    """
    Decorator to check authentication and pet access.
    Expects 'pet_id' to be present in request query params, body (via context), or args.
    Sets g.username upon success.
    """

    @login_required
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Authentication
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        # 2. Extract pet_id
        pet_id = None

        # Check context (flask-pydantic-spec)
        if hasattr(request, "context"):
            # Try query
            if hasattr(request.context, "query") and hasattr(request.context.query, "pet_id"):
                pet_id = request.context.query.pet_id
            # Try body
            elif hasattr(request.context, "body") and hasattr(request.context.body, "pet_id"):
                pet_id = request.context.body.pet_id

        # Fallback to pure request args if not found in context (e.g. if not validated yet or mixed)
        if not pet_id:
            pet_id = request.args.get("pet_id")

        # 3. Validate Access (and keep the pet doc — callers downstream that
        # need it, e.g. trend-anomaly notifications, reuse g.pet instead of
        # fetching it again).
        pet, access_error = validate_pet_access_and_get(pet_id, username)
        if pet is None:
            # error_response helper returns (json, status_code)
            return access_error[0], access_error[1]

        # 4. Set Context
        g.username = username
        g.pet_id = pet_id
        g.pet = pet

        return f(*args, **kwargs)

    return decorated_function


def require_record_access(collection_name, extra_filter=None, deleted_kind=None):
    """
    Decorator to check authentication and access to a specific record.
    The record_id must be the FIRST positional argument or 'id'/'record_id' keyword argument.
    Sets g.username, g.record, g.pet_id upon success.

    ``deleted_kind`` is for the routes that change a record (web/offline.py): the id of a record of this kind that was
    deleted, for a person who could see it, answers 409 ``record_deleted`` and not 404, because a device that edits a
    copy of something that is gone must drop the copy.
    """

    def decorator(f):
        @login_required
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Authentication
            username, auth_error = get_current_user()
            if auth_error:
                return auth_error[0], auth_error[1]

            # 2. Extract record_id
            # Flask passes path variables as kwargs usually
            record_id = kwargs.get("record_id") or kwargs.get("id")
            if not record_id and args:
                # If passed as positional (unlikely with named routes but possible)
                record_id = args[0]

            # 3. Validate Record Access
            # get_record_and_validate_access handles validation of record_id string too
            record, pet_id, access_error = get_record_and_validate_access(
                record_id, collection_name, username, extra_filter
            )
            if access_error:
                if deleted_kind:
                    from web.offline import deleted_by_id_answer

                    gone = deleted_by_id_answer(deleted_kind, record_id, username)
                    if gone:
                        return gone
                return access_error[0], access_error[1]

            # 4. Set Context
            g.username = username
            g.record = record
            g.pet_id = pet_id

            return f(*args, **kwargs)

        return decorated_function

    return decorator
