"""The user's own account: email, password, and recovery by email.

Links in letters carry a random token; only its SHA-256 is stored
(``account_tokens``), so a database leak doesn't hand out working links.
A token is single-use and short-lived (TTL index on ``expires_at``).
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

import bcrypt
from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response

import web.app as app
from web import mail
from web.app import api, limiter, logger
from web.auth import password_problem, signed_in_response
from web.errors import error_response
from web.legal import consent_needed
from web.messages import get_message
from web.account_deletion import delete_account, deletion_plan, plan_summary, was_deleted
from web.schemas import (
    AccountDeleteRequest,
    AccountDeletionPreviewResponse,
    AccountResponse,
    AuthTokensResponse,
    EmailChangeRequest,
    EmailVerifyRequest,
    ErrorResponse,
    PasswordChangeRequest,
    PasswordForgotRequest,
    PasswordForgotResponse,
    PasswordResetCheckResponse,
    PasswordResetRequest,
    SuccessResponse,
)
from web.security import (
    get_token_from_request,
    is_admin,
    login_required,
    revoke_user_sessions,
    verify_token,
    verify_user_credentials,
)

account_bp = Blueprint("account", __name__)

RESET_TTL = timedelta(hours=1)
VERIFY_TTL = timedelta(days=1)
# One reset letter per account this often, however many times it's asked.
RESET_RESEND_AFTER = timedelta(minutes=2)
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_token(username: str, purpose: str, ttl: timedelta, **extra) -> str:
    """A fresh link for ``purpose``; any earlier one of the same kind stops working."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    app.db.account_tokens.delete_many({"username": username, "purpose": purpose})
    app.db.account_tokens.insert_one(
        {
            "token_hash": _hash(token),
            "username": username,
            "purpose": purpose,
            "created_at": now,
            "expires_at": now + ttl,
            **extra,
        }
    )
    return token


def _take_token(token: str, purpose: str):
    """The token's record, removed so it can't be used twice; None if it's
    unknown, used or expired."""
    record = app.db.account_tokens.find_one_and_delete({"token_hash": _hash(token or ""), "purpose": purpose})
    if not record:
        return None
    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return record if expires_at > datetime.now(timezone.utc) else None


def _link_is_live(record: Optional[dict]) -> bool:
    """Whether a token's record still works: in time, and for an account that
    is there and can sign in."""
    if not record:
        return False
    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return False
    return app.db.users.find_one({"username": record["username"], "is_active": {"$ne": False}}, {"_id": 1}) is not None


def _email_taken(email: str, username: str) -> bool:
    """Confirmed on another account (one address recovers one account)."""
    return (
        app.db.users.find_one(
            {
                "username": {"$ne": username},
                "email_verified": True,
                "email": {"$regex": f"^{re.escape(email)}$", "$options": "i"},
            },
            {"_id": 1},
        )
        is not None
    )


def _mask(email: str) -> str:
    """v***@mail.ru: enough to recognise your own address, not to read someone's."""
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


def send_verification(username: str, email: str) -> None:
    token = _new_token(username, "verify_email", VERIFY_TTL, email=email)
    mail.send_mail(
        email,
        "Petzy: подтвердите почту",
        f"Здравствуйте!\n\n"
        f"Эту почту указали для аккаунта {username} в Petzy. Чтобы подтвердить её, откройте ссылку:\n\n"
        f"{mail.app_url('/verify-email?token=' + token)}\n\n"
        f"После этого на неё можно будет получить ссылку для смены пароля, если вы его забудете. "
        f"Ссылка работает сутки.\n\n"
        f"Если вы не регистрировались в Petzy, просто удалите это письмо.",
    )


def _notify(user: dict, subject: str, text: str) -> None:
    """A heads-up to the confirmed address; never blocks the change itself."""
    if not (user.get("email_verified") and user.get("email")) or not mail.mail_configured():
        return
    try:
        mail.send_mail(user["email"], subject, text)
    except Exception as e:
        logger.warning(f"Security notice not sent: user={user['username']}, error={e}")


def _account(user: dict) -> dict:
    return {
        "username": user["username"],
        "full_name": user.get("full_name") or "",
        "email": (user.get("email") or "") if user.get("email_verified") else "",
        "email_verified": bool(user.get("email_verified")),
        "pending_email": user.get("pending_email") or "",
        "mail_enabled": mail.mail_configured(),
        "privacy_consent_needed": consent_needed(user),
    }


@account_bp.route("/api/me/account", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=AccountResponse), tags=["account"])
def get_account():
    """The signed-in user's login, name and email state."""
    user = app.db.users.find_one({"username": request.current_user}) or {"username": request.current_user}
    return jsonify(_account(user))


@account_bp.route("/api/me/email", methods=["PUT"])
@limiter.limit("10 per hour")
@login_required
@api.validate(
    body=Request(EmailChangeRequest),
    resp=Response(HTTP_200=AccountResponse, HTTP_422=ErrorResponse, HTTP_503=ErrorResponse),
    tags=["account"],
)
def change_email():
    """Set, change or remove the recovery email. Needs the current password:
    whoever controls the email controls the account, so a borrowed phone
    with an open session mustn't be enough to change it."""
    username = request.current_user
    data = request.context.body  # type: ignore[attr-defined]
    if not verify_user_credentials(username, data.password):
        return error_response("account_wrong_password")
    user = app.db.users.find_one({"username": username})
    email = data.email.strip()

    if not email:
        app.db.users.update_one(
            {"username": username}, {"$set": {"email": "", "email_verified": False}, "$unset": {"pending_email": ""}}
        )
        app.db.account_tokens.delete_many({"username": username, "purpose": "verify_email"})
        return jsonify(_account(app.db.users.find_one({"username": username})))

    if not EMAIL_RE.match(email) or len(email) > 254:
        return error_response("account_email_invalid")
    if not mail.mail_configured():
        return error_response("mail_not_configured")
    if _email_taken(email, username):
        return error_response("account_email_taken")
    if user.get("email_verified") and (user.get("email") or "").lower() == email.lower():
        return jsonify(_account(user))

    app.db.users.update_one({"username": username}, {"$set": {"pending_email": email}})
    try:
        send_verification(username, email)
    except Exception as e:
        logger.error(f"Verification letter not sent: user={username}, error={e}")
        return error_response("mail_send_failed")
    return jsonify(_account(app.db.users.find_one({"username": username})))


@account_bp.route("/api/me/email/resend", methods=["POST"])
@limiter.limit("5 per hour")
@login_required
@api.validate(resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_503=ErrorResponse), tags=["account"])
def resend_verification():
    """Send the confirmation letter for the pending address again."""
    username = request.current_user
    user = app.db.users.find_one({"username": username}) or {}
    pending = user.get("pending_email")
    if not pending:
        return error_response("account_no_pending_email")
    if not mail.mail_configured():
        return error_response("mail_not_configured")
    try:
        send_verification(username, pending)
    except Exception as e:
        logger.error(f"Verification letter not sent: user={username}, error={e}")
        return error_response("mail_send_failed")
    return get_message("account_verification_sent")


@account_bp.route("/api/auth/email/verify", methods=["POST"])
@limiter.limit("30 per hour")
@api.validate(
    body=Request(EmailVerifyRequest),
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse),
    tags=["account"],
)
def verify_email():
    """The link from the letter. No session needed: it may be opened on
    another device than the one the address was typed on."""
    data = request.context.body  # type: ignore[attr-defined]
    record = _take_token(data.token, "verify_email")
    if not record:
        return error_response("account_link_invalid")
    username, email = record["username"], record["email"]
    user = app.db.users.find_one({"username": username, "is_active": {"$ne": False}})
    if not user or (user.get("pending_email") or "").lower() != email.lower():
        # Changed again (or removed) since this letter went out.
        return error_response("account_link_invalid")
    if _email_taken(email, username):
        return error_response("account_email_taken")

    old = dict(user)
    app.db.users.update_one(
        {"username": username},
        {"$set": {"email": email, "email_verified": True}, "$unset": {"pending_email": ""}},
    )
    if old.get("email_verified") and (old.get("email") or "").lower() != email.lower():
        _notify(
            old,
            "Petzy: почта аккаунта изменена",
            f"Для аккаунта {username} в Petzy теперь указана другая почта: {_mask(email)}.\n\n"
            f"Если это сделали не вы, напишите администратору Petzy.",
        )
    logger.info(f"Email verified: user={username}")
    return get_message("account_email_verified")


@account_bp.route("/api/auth/password/forgot", methods=["POST"])
@limiter.limit("5 per hour")
@api.validate(body=Request(PasswordForgotRequest), resp=Response(HTTP_200=PasswordForgotResponse), tags=["account"])
def forgot_password():
    """Send a reset link to the account's confirmed email.

    The answer is the same whether the login exists, has an email, or not:
    this form mustn't tell anyone which logins or addresses are real. The one
    thing it does add is ``already_sent``: the letter was asked for moments
    ago and no second one is on its way, and saying «sent» again would leave
    the person waiting for a letter that isn't coming.
    """
    data = request.context.body  # type: ignore[attr-defined]
    login = data.login.strip()
    if "@" in login:
        user = app.db.users.find_one(
            {"email_verified": True, "email": {"$regex": f"^{re.escape(login)}$", "$options": "i"}}
        )
    else:
        user = app.db.users.find_one({"username": login}) or app.db.users.find_one({"username": login.lower()})

    already_sent = False
    if user and user.get("is_active", True) and user.get("email_verified") and user.get("email"):
        recent = app.db.account_tokens.find_one(
            {
                "username": user["username"],
                "purpose": "reset",
                "created_at": {"$gt": datetime.now(timezone.utc) - RESET_RESEND_AFTER},
            }
        )
        if recent:
            already_sent = True
        elif mail.mail_configured():
            token = _new_token(user["username"], "reset", RESET_TTL)
            try:
                mail.send_mail(
                    user["email"],
                    "Petzy: новый пароль",
                    f"Здравствуйте!\n\n"
                    f"Для аккаунта {user['username']} в Petzy попросили сменить пароль. "
                    f"Чтобы задать новый, откройте ссылку:\n\n"
                    f"{mail.app_url('/reset-password?token=' + token)}\n\n"
                    f"Ссылка работает один час и только один раз.\n\n"
                    f"Если вы не просили сменить пароль, просто удалите это письмо: пароль останется прежним.",
                )
                logger.info(f"Password reset link sent: user={user['username']}")
            except Exception as e:
                logger.error(f"Password reset letter not sent: user={user['username']}, error={e}")
    return get_message("account_reset_requested", already_sent=already_sent)


@account_bp.route("/api/auth/password/reset/check", methods=["GET"])
@limiter.limit("30 per hour")
@api.validate(resp=Response(HTTP_200=PasswordResetCheckResponse), tags=["account"])
def check_reset_link():
    """Whether the letter's link can still set a new password.

    Asked when the screen opens, so a link that expired or was already spent
    is said at once instead of after the person picks a password. The token is
    only read here: the form still needs it.
    """
    record = app.db.account_tokens.find_one({"token_hash": _hash(request.args.get("token") or ""), "purpose": "reset"})
    return jsonify({"valid": _link_is_live(record)})


@account_bp.route("/api/auth/password/reset", methods=["POST"])
@limiter.limit("20 per hour")
@api.validate(
    body=Request(PasswordResetRequest),
    resp=Response(HTTP_200=AuthTokensResponse, HTTP_422=ErrorResponse),
    tags=["account"],
)
def reset_password():
    """Set a new password from the letter's link and sign in with it.
    Every other session of the account ends."""
    data = request.context.body  # type: ignore[attr-defined]
    # Checked against the link's account before the link is spent, so a
    # too-short password doesn't burn it.
    record = app.db.account_tokens.find_one({"token_hash": _hash(data.token or ""), "purpose": "reset"})
    if not record:
        return error_response("account_link_invalid")
    problem = password_problem(data.password, record["username"])
    if problem:
        return error_response(problem)
    record = _take_token(data.token, "reset")
    if not record:
        return error_response("account_link_invalid")
    username = record["username"]
    user = app.db.users.find_one({"username": username, "is_active": {"$ne": False}})
    if not user:
        return error_response("account_link_invalid")

    app.db.users.update_one(
        {"username": username},
        {"$set": {"password_hash": bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()}},
    )
    revoke_user_sessions(username)
    _notify(
        user,
        "Petzy: пароль изменён",
        f"Пароль аккаунта {username} в Petzy изменён по ссылке из письма.\n\n"
        f"Если это сделали не вы, сразу запросите новую ссылку на экране входа («Забыли пароль?») "
        f"и напишите администратору Petzy.",
    )
    logger.info(f"Password reset by link: user={username}")
    # The login comes back so the app can sign straight in with it.
    return signed_in_response("account_password_changed", username, username=username)


@account_bp.route("/api/me/password", methods=["PUT"])
@limiter.limit("10 per hour")
@login_required
@api.validate(
    body=Request(PasswordChangeRequest),
    resp=Response(HTTP_200=AuthTokensResponse, HTTP_422=ErrorResponse),
    tags=["account"],
)
def change_password():
    """Change the password knowing the current one. Other sessions end; this
    one continues with fresh cookies."""
    username = request.current_user
    data = request.context.body  # type: ignore[attr-defined]
    if not verify_user_credentials(username, data.current_password):
        return error_response("account_wrong_password")
    problem = password_problem(data.new_password, username)
    if problem:
        return error_response(problem)
    app.db.users.update_one(
        {"username": username},
        {"$set": {"password_hash": bcrypt.hashpw(data.new_password.encode(), bcrypt.gensalt()).decode()}},
    )
    revoke_user_sessions(username)
    user = app.db.users.find_one({"username": username}) or {}
    _notify(
        user,
        "Petzy: пароль изменён",
        f"Пароль аккаунта {username} в Petzy изменён в настройках.\n\n"
        f"Если это сделали не вы, запросите новую ссылку на экране входа («Забыли пароль?») "
        f"и напишите администратору Petzy.",
    )
    logger.info(f"Password changed: user={username}")
    return signed_in_response("account_password_changed", username)


@account_bp.route("/api/me/account/deletion", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=AccountDeletionPreviewResponse), tags=["account"])
def deletion_preview():
    """What deleting the account would do: pets deleted, handed over, left."""
    username = request.current_user
    return jsonify({"can_delete": not is_admin(username), **plan_summary(deletion_plan(username))})


def login_or_already_deleted(view):
    """``@login_required``, with the one answer a signed-out request may get.

    ``@login_required`` refuses the token of an account that is not there any
    more, which is right for every other route. Here that absence is the very
    thing the request is about: the DELETE went through and its answer was
    lost on the way (a closed tab, a dead connection), so pressing the button
    again is the same request and answers the same way. Nothing of any other
    account is read or touched to give it.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        token = get_token_from_request()
        payload = verify_token(token, "access") if token else None
        username = payload.get("username") if payload else None
        if username and was_deleted(username):
            logger.info(f"Account deletion repeated: user={username}")
            return _deleted_answer()
        return login_required(view)(*args, **kwargs)

    return wrapper


@account_bp.route("/api/me/account", methods=["DELETE"])
@limiter.limit("10 per hour")
@login_or_already_deleted
@api.validate(
    body=Request(AccountDeleteRequest),
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["account"],
)
def delete_own_account():
    """Delete the account for good, confirmed with the password.

    A pet shared with someone goes to the first of them, the rest are
    deleted with their records and files (see GET /api/me/account/deletion).
    Every session ends; the web app's cookies are cleared.
    """
    username = request.current_user
    data = request.context.body  # type: ignore[attr-defined]
    if is_admin(username):
        return error_response("account_admin_undeletable")
    if not verify_user_credentials(username, data.password):
        return error_response("account_wrong_password")

    user = app.db.users.find_one({"username": username}) or {}
    heirs = {}
    try:
        plan = delete_account(username)
    except Exception as e:
        logger.error(f"Account deletion failed: user={username}, error={e}")
        return error_response("account_delete_failed")
    for pet, heir in plan["transferred"]:
        heirs.setdefault(heir, []).append(pet.get("name", ""))

    _notify(
        user,
        "Petzy: аккаунт удалён",
        f"Аккаунт {username} в Petzy удалён вместе с его данными.\n\n"
        f"Если это сделали не вы, напишите администратору Petzy.",
    )
    for heir, names in heirs.items():
        pets = ", ".join(f"«{name}»" for name in names)
        _notify(
            app.db.users.find_one({"username": heir}) or {},
            "Petzy: вам передали питомца",
            f"Аккаунт {username} в Petzy удалён, и теперь владелец вы: {pets}. "
            f"Все записи, лекарства и документы остались на месте.",
        )

    return _deleted_answer()


def _deleted_answer():
    """The answer a finished deletion gives, word for word: the repeat must
    not be tellable from the first one, and there are no cookies left to
    clear a second time."""
    response, status = get_message("account_deleted")
    response.set_cookie("access_token", "", max_age=0)
    response.set_cookie("refresh_token", "", max_age=0)
    return response, status


@account_bp.route("/api/dev/outbox", methods=["GET"])
def dev_outbox():
    """Letters kept by MAIL_OUTBOX=memory, for local runs only: 404 otherwise."""
    if not mail._outbox_mode():
        return error_response("not_found")
    return jsonify({"letters": mail.OUTBOX[-20:]})
