"""The user's own account: email, password, and recovery by email.

Links in letters carry a random token; only its SHA-256 is stored
(``account_tokens``), so a database leak doesn't hand out working links.
A token is single-use and short-lived (TTL index on ``expires_at``).
"""

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

import bcrypt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response

import web.app as app
from web import login_lockout, mail
from web.app import api, limiter, logger
from web.auth import password_problem, signed_in_response
from web.configs import JWT_CONFIG
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
# Confirmation letters counted per address at sign-up: this many in this window (reserve_verification_letter).
VERIFY_LETTERS_PER_ADDRESS = 3
VERIFY_LETTERS_WINDOW = timedelta(hours=24)
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


# One mailbox has several spellings at gmail.com and googlemail.com: dots in the name, a part after «+», the other
# domain name. The letter limit counts them as one address (see _counted_address).
GMAIL_DOMAINS = ("gmail.com", "googlemail.com")


def _counted_address(email: str) -> str:
    """The address as the letter limit counts it, in lower case.

    At gmail.com and googlemail.com the dots in the name and anything after «+» are left out, and the domain is
    gmail.com: v.era+1@googlemail.com counts as vera@gmail.com. Other domains are kept as typed.
    """
    address = email.strip().lower()
    local, at, domain = address.rpartition("@")
    if at and domain in GMAIL_DOMAINS:
        return local.split("+", 1)[0].replace(".", "") + "@gmail.com"
    return address


def _address_key(email: str) -> str:
    """How an address is kept in ``verification_mail_log``: an HMAC of it as ``_counted_address`` gives it, under a
    key derived from the server's secret. The log holds no readable address, and a copy of the collection alone
    cannot be matched to one."""
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"petzy verification letter").derive(
        JWT_CONFIG["secret_key"].encode("utf-8")
    )
    return hmac.new(key, _counted_address(email).encode("utf-8"), hashlib.sha256).hexdigest()


def reserve_verification_letter(email: str):
    """Count one confirmation letter to ``email`` before it goes out; return the id of the row that counts it.

    None when the address has had its letters for the day: the row is taken back, so a refusal counts for nothing.
    The row is written before it is counted, so two sign-ups at the same moment cannot both take the last place.
    A letter counted here stays counted if sending it then fails.
    """
    now = datetime.now(timezone.utc)
    key = _address_key(email)
    row = app.db.verification_mail_log.insert_one({"address_key": key, "expires_at": now + VERIFY_LETTERS_WINDOW})
    letters = app.db.verification_mail_log.count_documents({"address_key": key, "expires_at": {"$gt": now}})
    if letters > VERIFY_LETTERS_PER_ADDRESS:
        app.db.verification_mail_log.delete_one({"_id": row.inserted_id})
        return None
    return row.inserted_id


def release_verification_letter(letter_id) -> None:
    """Take back a counted letter that will not go out, because its account was not made."""
    app.db.verification_mail_log.delete_one({"_id": letter_id})


def letter_limit_response():
    """The 429 for an address whose letters are used up for the day. ``retry_after`` and ``Retry-After`` give the
    window's length in seconds, as for every 429 (web/app.py)."""
    window = int(VERIFY_LETTERS_WINDOW.total_seconds())
    response, status = error_response("register_letter_limit")
    body = response.get_json()
    body["retry_after"] = window
    response = jsonify(body)
    response.headers["Retry-After"] = str(window)
    return response, status


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
    """The signed-in user's login, name and email state.

    Whether the address is confirmed and whether the current privacy policy has been agreed to, which is what the app asks about before anything else.
    """
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
    """Set, change or remove the recovery email.

    Needs the current password: whoever controls the email controls the account,
    so a borrowed phone with an open session mustn't be enough to change it.
    A new address goes to `pending_email` and a letter with a link (valid for a day) is sent to it;
    `email` changes only after POST /api/auth/email/verify, and until then the old address stays the working one.
    The address that is already confirmed answers with the account unchanged. An empty ``email`` removes the
    address and any pending one at once, mail configured or not. Errors: 422 ``account_wrong_password``,
    ``account_email_invalid``, ``account_email_taken``; 429 ``register_letter_limit`` when three letters already went
    to that address in the last day (then nothing changes); 503 ``mail_not_configured`` or ``mail_send_failed``
    (then ``pending_email`` is already saved and the letter can be sent again).
    """
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
    # Counted before the letter is due, as at sign-up: a refused change sets no pending address.
    if reserve_verification_letter(email) is None:
        logger.warning(f"Address change refused, letters to the address used up for the day: user={username}")
        return letter_limit_response()

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
    """Send the confirmation letter for the pending address again.

    For an address that was typed but not confirmed. The letter goes only to the new address, and while it is unconfirmed the old one stays the working one. The new letter's link replaces the earlier one, which stops working. Every letter to one address counts in the same three a day as at sign-up: a fourth answers 429 ``register_letter_limit``.
    """
    username = request.current_user
    user = app.db.users.find_one({"username": username}) or {}
    pending = user.get("pending_email")
    if not pending:
        return error_response("account_no_pending_email")
    if not mail.mail_configured():
        return error_response("mail_not_configured")
    # Counted before the letter goes, like every confirmation letter (see reserve_verification_letter).
    if reserve_verification_letter(pending) is None:
        logger.warning(f"Letter refused, letters to the address used up for the day: user={username}")
        return letter_limit_response()
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
    """Confirm an email address from the link in the letter.

    No session needed: the link may be opened on another device than the one
    the address was typed on. The link lives a day; an unknown, used or expired link, one replaced by a newer
    letter, one for an address changed since, or one of a switched-off account answers 422
    ``account_link_invalid``. An address confirmed meanwhile on another account answers 422
    ``account_email_taken`` (the link is spent by then). If another address was confirmed before, a notice
    goes to it.
    """
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
@api.validate(body=Request(PasswordForgotRequest), resp=Response(HTTP_200=SuccessResponse), tags=["account"])
def forgot_password():
    """Send a reset link to the account's confirmed email.

    The answer must not tell anyone which logins or addresses are real, nor that a letter was asked for moments
    ago: it is the same 200 and the same text for a real account and a made-up one, asked once or again.
    A value with «@» is matched, any case, against confirmed addresses only; otherwise the exact login, then the
    lowercased one. At most one letter per account every 2 minutes, and a request inside that gap sends nothing;
    the link lives an hour. Nothing is sent if mail is not configured or sending fails, and the answer is still
    200. The limit counts requests, not letters.
    """
    data = request.context.body  # type: ignore[attr-defined]
    login = data.login.strip()
    asked_by_email = "@" in login
    if asked_by_email:
        user = app.db.users.find_one(
            {"email_verified": True, "email": {"$regex": f"^{re.escape(login)}$", "$options": "i"}}
        )
    else:
        user = app.db.users.find_one({"username": login}) or app.db.users.find_one({"username": login.lower()})

    if user and user.get("is_active", True) and user.get("email_verified") and user.get("email"):
        recent = app.db.account_tokens.find_one(
            {
                "username": user["username"],
                "purpose": "reset",
                "created_at": {"$gt": datetime.now(timezone.utc) - RESET_RESEND_AFTER},
            }
        )
        # A letter asked for moments ago is not sent again, and the answer does not say so.
        if not recent and mail.mail_configured():
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
    return get_message("account_reset_requested")


@account_bp.route("/api/auth/password/reset/check", methods=["GET"])
@limiter.limit("30 per hour")
@api.validate(resp=Response(HTTP_200=PasswordResetCheckResponse), tags=["account"])
def check_reset_link():
    """Whether the letter's link can still set a new password.

    Asked when the screen opens, so a link that expired or was already spent
    is said at once instead of after the person picks a password. The token is
    only read here: the form still needs it. It comes as the query parameter `token`;
    a missing or unknown one answers `{"valid": false}`.
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

    Every other session of the account ends. The link is checked before it is
    spent, so a password the server refuses does not burn it. The link lives an hour;
    an expired, spent or unknown one, or one of a switched-off account, answers 422 `account_link_invalid`.
    Пароль: от 8 символов и не длиннее 72 байт (36 русских букв), не из частых, не совпадает с логином и в нём хотя бы три разных символа; иначе 422 `register_password_short`, `register_password_long` или `register_password_weak`. A notice goes to the confirmed address.
    """
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
    """Change the password knowing the current one.

    Other sessions end. This one continues: the web app gets fresh cookies, a native app (no Origin header) gets
    new `access_token` and `refresh_token` in the body and must replace its old ones, which stop working.
    A wrong ``current_password`` answers 422 ``account_wrong_password`` before the password rules are checked.
    Пароль: от 8 символов и не длиннее 72 байт (36 русских букв), не из частых, не совпадает с логином и в нём хотя бы три разных символа; иначе 422 `register_password_short`, `register_password_long` или `register_password_weak`. A notice goes to the confirmed address.
    """
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
    """What deleting the account would do: pets deleted, handed over, left.

    Read it before calling ``DELETE /api/me/account``. Pets owned alone are deleted with their records and files (`deleted`). A pet shared with somebody goes to the first of them who can still sign in, otherwise to the first who has an account at all (`transferred`, `new_owner`). Other people's pets you were invited to stay with their owner, and you lose access (`left`, `owner`). Nothing here changes anything on its own.
    """
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

    A pet shared with someone goes to the first of them who can still sign in, the rest are
    deleted with their records and files (see GET /api/me/account/deletion).
    Every session ends; the web app's cookies are cleared. Letters go to the account's confirmed
    address and to every new owner, when mail is configured. The administrator cannot be deleted (422
    `account_admin_undeletable`, checked first); a wrong password answers 422 `account_wrong_password`.
    The heir is the first member who can still sign in, otherwise the first who has an account at all.
    Repeating the call after a successful deletion (a lost answer) answers the same 200 while the old access
    token is still valid (15 minutes); later, or once the login is registered again, it answers 401.
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


def _dev_tools_on() -> bool:
    """The dev routes exist only on the local stand: PETZY_DEV_TOOLS=1 and MAIL_OUTBOX=memory
    together. Either one alone answers 404, so a MAIL_OUTBOX left on a server opens nothing."""
    return os.getenv("PETZY_DEV_TOOLS") == "1" and mail._outbox_mode()


@account_bp.route("/api/dev/outbox", methods=["GET"])
def dev_outbox():
    """Letters kept by MAIL_OUTBOX=memory, for local runs only: 404 otherwise."""
    if not _dev_tools_on():
        return error_response("not_found")
    return jsonify({"letters": mail.OUTBOX[-20:]})


@account_bp.route("/api/dev/reset-limits", methods=["POST"])
def dev_reset_limits():
    """Every rate-limit counter, letter count and wrong-password lock back to zero, for local runs only: 404 otherwise.

    A limit counts per address, and on the stand every browser check comes from the same one:
    five password letters and five sign-ups an hour are spent by the first run, and the second
    one starts on a spent limit and checks nothing. With this every run starts from the same
    place. Gated the way /api/dev/outbox is gated (the two switches together mean "this is the local
    stand"), so the endpoint answers 404 in production and no one can drop a real person's counters.
    A login locked by wrong passwords starts again too (web/login_lockout.py).
    """
    if not _dev_tools_on():
        return error_response("not_found")
    limiter.reset()
    # The letter counts per address are limits too: on the stand a browser check starts them from zero as well.
    app.db.verification_mail_log.delete_many({})
    # A check that guessed wrong would hold its login for fifteen minutes: the locks go with the counters.
    login_lockout.clear_all()
    return jsonify({"message": "Счётчики ограничений обнулены", "success": True})
