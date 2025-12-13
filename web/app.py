"""Flask web application for cat health tracking."""

import csv
import io
import os
import time
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote

import bcrypt
import jwt
from flask import Flask, jsonify, make_response, redirect, render_template, request, url_for

from web.db import db
from gridfs import GridFS

# Initialize GridFS for file storage
fs = GridFS(db)

# Configure Flask app with proper template and static folders
app = Flask(
    __name__,
    template_folder='templates',
    static_folder='static'
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
app.config['JSON_AS_ASCII'] = False
# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", app.secret_key)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Access token expires in 15 minutes
REFRESH_TOKEN_EXPIRE_DAYS = 7  # Refresh token expires in 7 days

# Authentication credentials - REQUIRED from environment
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")

# Validate required environment variables
if not ADMIN_PASSWORD_HASH:
    raise RuntimeError(
        "ADMIN_PASSWORD_HASH environment variable is required! "
        "To generate hash: python -c \"import bcrypt; print(bcrypt.hashpw('your_password'.encode(), bcrypt.gensalt()).decode())\""
    )

# Use a default user_id for web user (can be any number, just for data storage)
DEFAULT_USER_ID = 0

# Helper function to verify user credentials
def verify_user_credentials(username: str, password: str) -> bool:
    """Verify user credentials from database or fallback to admin."""
    # First, try to find user in database
    user = db["users"].find_one({"username": username, "is_active": True})
    if user:
        try:
            return bcrypt.checkpw(password.encode(), user["password_hash"].encode())
        except (ValueError, TypeError, KeyError):
            return False
    
    # Fallback to admin credentials for backward compatibility
    if username == ADMIN_USERNAME:
        try:
            return bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH.encode())
        except (ValueError, TypeError):
            return False
    
    return False

# Helper function to ensure default admin user exists
def ensure_default_admin():
    """Ensure default admin user exists in database."""
    admin_user = db["users"].find_one({"username": ADMIN_USERNAME})
    if not admin_user:
        # Create default admin user
        db["users"].insert_one({
            "username": ADMIN_USERNAME,
            "password_hash": ADMIN_PASSWORD_HASH,
            "full_name": "Administrator",
            "email": "",
            "created_at": datetime.utcnow(),
            "created_by": "system",
            "is_active": True
        })

# Initialize default admin on startup
ensure_default_admin()

# Rate limiting for login attempts
login_attempts = {}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_TIME = 300  # 5 minutes in seconds


def create_access_token(username: str) -> str:
    """Create JWT access token."""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "username": username,
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(username: str) -> str:
    """Create JWT refresh token and store it in database."""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "username": username,
        "exp": expire,
        "type": "refresh"
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    # Store refresh token in database
    db["refresh_tokens"].insert_one({
        "token": token,
        "username": username,
        "created_at": datetime.utcnow(),
        "expires_at": expire
    })
    
    return token


def verify_token(token: str, token_type: str = "access") -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_token_from_request():
    """Extract token from Authorization header or cookie."""
    # Try Authorization header first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    
    # Try cookie
    return request.cookies.get("access_token")


def try_refresh_access_token():
    """Try to refresh access token using refresh token. Returns new access token or None."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return None
    
    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")
    if not payload:
        return None
    
    # Check if token exists in database
    token_record = db["refresh_tokens"].find_one({"token": refresh_token})
    if not token_record:
        return None
    
    username = payload.get("username")
    return create_access_token(username)


def login_required(f):
    """Decorator to require valid JWT access token."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()
        payload = None
        new_token = None
        
        if token:
            payload = verify_token(token, "access")
        
        if not payload:
            # Token missing or invalid, try to refresh
            new_token = try_refresh_access_token()
            if new_token:
                payload = verify_token(new_token, "access")
                if not payload:
                    new_token = None
        
        if not payload:
            # No valid token available
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized", "message": "Token required"}), 401
            return redirect(url_for("login"))
        
        # We have valid token (either original or refreshed)
        request.current_user = payload.get("username")
        
        # Execute the function
        response = f(*args, **kwargs)
        
        # If we refreshed the token, set it in the response cookie
        if new_token:
            # Wrap response if needed to set cookie
            if isinstance(response, tuple):
                response_obj, status_code = response[0], response[1] if len(response) > 1 else 200
                response = make_response(response_obj, status_code)
            elif not hasattr(response, 'set_cookie'):
                response = make_response(response)
            
            response.set_cookie(
                "access_token",
                new_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                httponly=True,
                secure=False,
                samesite="Lax"
            )
        
        return response

    return decorated_function


@app.route("/")
def index():
    """Redirect to login or dashboard."""
    token = get_token_from_request()
    if token:
        payload = verify_token(token, "access")
        if payload:
            return redirect(url_for("dashboard"))
    
    # Try to refresh using refresh token
    new_token = try_refresh_access_token()
    if new_token:
        payload = verify_token(new_token, "access")
        if payload:
            response = make_response(redirect(url_for("dashboard")))
            response.set_cookie(
                "access_token",
                new_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                httponly=True,
                secure=False,
                samesite="Lax"
            )
            return response
    
    return redirect(url_for("login"))


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """API endpoint for login - returns JWT tokens."""
    data = request.get_json()
    username = data.get("username", "").strip() if data else ""
    password = data.get("password", "") if data else ""
    client_ip = request.remote_addr
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    # Check rate limiting
    if client_ip in login_attempts:
        attempts_data = login_attempts[client_ip]
        if attempts_data["locked_until"] > time.time():
            remaining_time = int((attempts_data["locked_until"] - time.time()) / 60) + 1
            return jsonify({"error": f"Too many attempts. Try again in {remaining_time} minutes"}), 429
        elif attempts_data["count"] >= MAX_LOGIN_ATTEMPTS:
            if time.time() - attempts_data["last_attempt"] > LOGIN_LOCKOUT_TIME:
                login_attempts[client_ip] = {"count": 0, "last_attempt": time.time(), "locked_until": 0}
            else:
                remaining_time = int((attempts_data["locked_until"] - time.time()) / 60) + 1
                return jsonify({"error": f"Too many attempts. Try again in {remaining_time} minutes"}), 429
    
    # Verify username and password
    if verify_user_credentials(username, password):
        # Successful login - reset attempts
        if client_ip in login_attempts:
            del login_attempts[client_ip]
        
        # Create tokens
        access_token = create_access_token(username)
        refresh_token = create_refresh_token(username)
        
        response = jsonify({
            "success": True,
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token
        })
        
        # Set tokens in httpOnly cookies
        response.set_cookie(
            "access_token",
            access_token,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="Lax"
        )
        response.set_cookie(
            "refresh_token",
            refresh_token,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="Lax"
        )
        
        return response
    
    # Failed login
    if client_ip not in login_attempts:
        login_attempts[client_ip] = {"count": 0, "last_attempt": time.time(), "locked_until": 0}
    
    login_attempts[client_ip]["count"] += 1
    login_attempts[client_ip]["last_attempt"] = time.time()
    
    if login_attempts[client_ip]["count"] >= MAX_LOGIN_ATTEMPTS:
        login_attempts[client_ip]["locked_until"] = time.time() + LOGIN_LOCKOUT_TIME
    
    return jsonify({"error": "Invalid username or password"}), 401


@app.route("/api/auth/refresh", methods=["POST"])
def api_refresh():
    """Refresh access token using refresh token."""
    refresh_token = request.cookies.get("refresh_token") or (request.get_json() or {}).get("refresh_token")
    
    if not refresh_token:
        return jsonify({"error": "Refresh token required"}), 401
    
    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")
    if not payload:
        return jsonify({"error": "Invalid or expired refresh token"}), 401
    
    # Check if token exists in database
    token_record = db["refresh_tokens"].find_one({"token": refresh_token})
    if not token_record:
        return jsonify({"error": "Refresh token not found"}), 401
    
    username = payload.get("username")
    
    # Create new access token
    access_token = create_access_token(username)
    
    response = jsonify({
        "success": True,
        "access_token": access_token
    })
    
    response.set_cookie(
        "access_token",
        access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False,
        samesite="Lax"
    )
    
    return response


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """Logout - invalidate refresh token."""
    refresh_token = request.cookies.get("refresh_token")
    
    if refresh_token:
        # Remove refresh token from database
        db["refresh_tokens"].delete_one({"token": refresh_token})
    
    response = jsonify({"success": True, "message": "Logged out"})
    response.set_cookie("access_token", "", max_age=0)
    response.set_cookie("refresh_token", "", max_age=0)
    
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page."""
    # Check if already logged in
    token = get_token_from_request()
    if token:
        payload = verify_token(token, "access")
        if payload:
            return redirect(url_for("dashboard"))
    
    # If no access token, try to refresh using refresh token
    new_token = try_refresh_access_token()
    if new_token:
        payload = verify_token(new_token, "access")
        if payload:
            response = make_response(redirect(url_for("dashboard")))
            response.set_cookie(
                "access_token",
                new_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                httponly=True,
                secure=False,
                samesite="Lax"
            )
            return response
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        client_ip = request.remote_addr
        
        if not username or not password:
            return render_template("login.html", error="Введите логин и пароль")
        
        # Check rate limiting
        if client_ip in login_attempts:
            attempts_data = login_attempts[client_ip]
            if attempts_data["locked_until"] > time.time():
                remaining_time = int((attempts_data["locked_until"] - time.time()) / 60) + 1
                return render_template("login.html", error=f"Слишком много попыток. Попробуйте через {remaining_time} минут")
            elif attempts_data["count"] >= MAX_LOGIN_ATTEMPTS:
                if time.time() - attempts_data["last_attempt"] > LOGIN_LOCKOUT_TIME:
                    login_attempts[client_ip] = {"count": 0, "last_attempt": time.time(), "locked_until": 0}
                else:
                    remaining_time = int((attempts_data["locked_until"] - time.time()) / 60) + 1
                    return render_template("login.html", error=f"Слишком много попыток. Попробуйте через {remaining_time} минут")
        
        # Verify username and password
        if verify_user_credentials(username, password):
            # Successful login - reset attempts
            if client_ip in login_attempts:
                del login_attempts[client_ip]
            
            # Create tokens
            access_token = create_access_token(username)
            refresh_token = create_refresh_token(username)
            
            # Create response with redirect
            response = make_response(redirect(url_for("dashboard")))
            
            # Set tokens in httpOnly cookies
            response.set_cookie(
                "access_token",
                access_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="Lax"
            )
            response.set_cookie(
                "refresh_token",
                refresh_token,
                max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="Lax"
            )
            
            return response
        
        # Failed login
        if client_ip not in login_attempts:
            login_attempts[client_ip] = {"count": 0, "last_attempt": time.time(), "locked_until": 0}
        
        login_attempts[client_ip]["count"] += 1
        login_attempts[client_ip]["last_attempt"] = time.time()
        
        if login_attempts[client_ip]["count"] >= MAX_LOGIN_ATTEMPTS:
            login_attempts[client_ip]["locked_until"] = time.time() + LOGIN_LOCKOUT_TIME
        
        return render_template("login.html", error="Неверный логин или пароль")
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Logout and clear tokens."""
    # Call API logout endpoint
    api_logout()
    return redirect(url_for("login"))


# Helper function to check if user is admin
def is_admin(username: str) -> bool:
    """Check if user is admin."""
    return username == ADMIN_USERNAME

# Decorator for admin-only endpoints
def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        username = getattr(request, 'current_user', None)
        if not username or not is_admin(username):
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function


@app.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard page."""
    username = getattr(request, 'current_user', 'admin')
    return render_template("dashboard.html", username=username)


# Helper function to check pet access
def check_pet_access(pet_id, username):
    """Check if user has access to pet."""
    try:
        from bson import ObjectId
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return False
        # User is owner or in shared_with
        return pet.get("owner") == username or username in pet.get("shared_with", [])
    except Exception:
        return False


@app.route("/api/pets", methods=["GET"])
@login_required
def get_pets():
    """Get list of all pets accessible to current user."""
    username = getattr(request, 'current_user', None)
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Get pets where user is owner or in shared_with
    pets = list(db["pets"].find({
        "$or": [
            {"owner": username},
            {"shared_with": username}
        ]
    }).sort("created_at", -1))
    
    for pet in pets:
        pet["_id"] = str(pet["_id"])
        if isinstance(pet.get("birth_date"), datetime):
            pet["birth_date"] = pet["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet.get("created_at"), datetime):
            pet["created_at"] = pet["created_at"].strftime("%Y-%m-%d %H:%M")
        
        # Add photo URL if file exists
        if pet.get("photo_file_id"):
            pet["photo_url"] = url_for('get_pet_photo', pet_id=pet["_id"], _external=False)
    
    return jsonify({"pets": pets})


@app.route("/api/pets", methods=["POST"])
@login_required
def create_pet():
    """Create a new pet."""
    try:
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Handle form data with file upload
        if request.content_type and 'multipart/form-data' in request.content_type:
            name = request.form.get("name", "").strip()
            if not name:
                return jsonify({"error": "Имя животного обязательно"}), 400
            
            # Handle photo file upload
            photo_file_id = None
            if 'photo_file' in request.files:
                photo_file = request.files['photo_file']
                if photo_file.filename:
                    from bson import ObjectId
                    photo_file_id = str(fs.put(photo_file, filename=photo_file.filename, content_type=photo_file.content_type))
            
            # Parse birth_date if provided
            birth_date = None
            if request.form.get("birth_date"):
                try:
                    birth_date = datetime.strptime(request.form.get("birth_date"), "%Y-%m-%d")
                except ValueError:
                    pass
            
            pet_data = {
                "name": name,
                "breed": request.form.get("breed", "").strip(),
                "birth_date": birth_date,
                "gender": request.form.get("gender", "").strip(),
                "photo_file_id": str(photo_file_id) if photo_file_id else None,
                "owner": username,
                "shared_with": [],
                "access_requests": [],
                "created_at": datetime.utcnow(),
                "created_by": username
            }
        else:
            # Handle JSON data (backward compatibility)
            data = request.get_json()
            name = data.get("name", "").strip()
            if not name:
                return jsonify({"error": "Имя животного обязательно"}), 400
            
            # Parse birth_date if provided
            birth_date = None
            if data.get("birth_date"):
                try:
                    birth_date = datetime.strptime(data.get("birth_date"), "%Y-%m-%d")
                except ValueError:
                    pass
            
            pet_data = {
                "name": name,
                "breed": data.get("breed", "").strip(),
                "birth_date": birth_date,
                "gender": data.get("gender", "").strip(),
                "photo_url": data.get("photo_url", "").strip(),
                "owner": username,
                "shared_with": [],
                "access_requests": [],
                "created_at": datetime.utcnow(),
                "created_by": username
            }
        
        result = db["pets"].insert_one(pet_data)
        pet_data["_id"] = str(result.inserted_id)
        if isinstance(pet_data.get("birth_date"), datetime):
            pet_data["birth_date"] = pet_data["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet_data.get("created_at"), datetime):
            pet_data["created_at"] = pet_data["created_at"].strftime("%Y-%m-%d %H:%M")
        
        return jsonify({"success": True, "pet": pet_data, "message": "Животное создано"}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pets/<pet_id>", methods=["GET"])
@login_required
def get_pet(pet_id):
    """Get pet information."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Check access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        pet["_id"] = str(pet["_id"])
        if isinstance(pet.get("birth_date"), datetime):
            pet["birth_date"] = pet["birth_date"].strftime("%Y-%m-%d")
        if isinstance(pet.get("created_at"), datetime):
            pet["created_at"] = pet["created_at"].strftime("%Y-%m-%d %H:%M")
        
        # Add photo URL if file exists
        if pet.get("photo_file_id"):
            pet["photo_url"] = url_for('get_pet_photo', pet_id=pet["_id"], _external=False)
        
        # Add current user info for frontend
        pet["current_user_is_owner"] = pet.get("owner") == username
        
        return jsonify({"pet": pet})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pets/<pet_id>", methods=["PUT"])
@login_required
def update_pet(pet_id):
    """Update pet information."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Only owner can update
        if pet.get("owner") != username:
            return jsonify({"error": "Только владелец может изменять информацию о животном"}), 403
        
        # Handle form data with file upload
        if request.content_type and 'multipart/form-data' in request.content_type:
            name = request.form.get("name", "").strip()
            if not name:
                return jsonify({"error": "Имя животного обязательно"}), 400
            
            # Handle photo file upload
            photo_file_id = pet.get("photo_file_id")  # Keep existing if no new file
            
            if 'photo_file' in request.files:
                photo_file = request.files['photo_file']
                
                if photo_file.filename:
                    # Delete old photo if exists
                    old_photo_id = pet.get("photo_file_id")
                    if old_photo_id:
                        try:
                            from bson import ObjectId
                            fs.delete(ObjectId(old_photo_id))
                        except:
                            pass
                    
                    # Upload new photo
                    from bson import ObjectId
                    photo_file_id = str(fs.put(photo_file, filename=photo_file.filename, content_type=photo_file.content_type))
                elif request.form.get("remove_photo") == "true":
                    # Remove photo
                    old_photo_id = pet.get("photo_file_id")
                    if old_photo_id:
                        try:
                            fs.delete(ObjectId(old_photo_id))
                        except:
                            pass
                    photo_file_id = None
            
            # Parse birth_date if provided
            birth_date = None
            if request.form.get("birth_date"):
                try:
                    birth_date = datetime.strptime(request.form.get("birth_date"), "%Y-%m-%d")
                except ValueError:
                    pass
            
            update_data = {
                "name": name,
                "breed": request.form.get("breed", "").strip(),
                "birth_date": birth_date,
                "gender": request.form.get("gender", "").strip(),
            }
            if photo_file_id is not None:
                update_data["photo_file_id"] = photo_file_id
            elif "photo_file_id" in request.form and request.form.get("photo_file_id") == "":
                update_data["photo_file_id"] = None
        else:
            # Handle JSON data (backward compatibility)
            data = request.get_json()
            name = data.get("name", "").strip()
            if not name:
                return jsonify({"error": "Имя животного обязательно"}), 400
            
            # Parse birth_date if provided
            birth_date = None
            if data.get("birth_date"):
                try:
                    birth_date = datetime.strptime(data.get("birth_date"), "%Y-%m-%d")
                except ValueError:
                    pass
            
            update_data = {
                "name": name,
                "breed": data.get("breed", "").strip(),
                "birth_date": birth_date,
                "gender": data.get("gender", "").strip(),
                "photo_url": data.get("photo_url", "").strip()
            }
        
        result = db["pets"].update_one(
            {"_id": ObjectId(pet_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Животное не найдено"}), 404
        
        return jsonify({"success": True, "message": "Информация о животном обновлена"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# API endpoints for users (admin only)
@app.route("/api/users", methods=["GET"])
@login_required
@admin_required
def get_users():
    """Get list of all users (admin only)."""
    users = list(db["users"].find({}).sort("created_at", -1))
    
    for user in users:
        user["_id"] = str(user["_id"])
        # Don't return password hash
        user.pop("password_hash", None)
        if isinstance(user.get("created_at"), datetime):
            user["created_at"] = user["created_at"].strftime("%Y-%m-%d %H:%M")
    
    return jsonify({"users": users})


@app.route("/api/users", methods=["POST"])
@login_required
@admin_required
def create_user():
    """Create a new user (admin only)."""
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        full_name = data.get("full_name", "").strip()
        email = data.get("email", "").strip()
        
        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400
        
        # Check if user already exists
        existing = db["users"].find_one({"username": username})
        if existing:
            return jsonify({"error": "Пользователь с таким именем уже существует"}), 400
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        
        current_user = getattr(request, 'current_user', 'admin')
        
        user_data = {
            "username": username,
            "password_hash": password_hash,
            "full_name": full_name,
            "email": email,
            "created_at": datetime.utcnow(),
            "created_by": current_user,
            "is_active": True
        }
        
        result = db["users"].insert_one(user_data)
        user_data["_id"] = str(result.inserted_id)
        user_data.pop("password_hash", None)
        if isinstance(user_data.get("created_at"), datetime):
            user_data["created_at"] = user_data["created_at"].strftime("%Y-%m-%d %H:%M")
        
        return jsonify({"success": True, "user": user_data, "message": "Пользователь создан"}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/users/<username>", methods=["GET"])
@login_required
@admin_required
def get_user(username):
    """Get user information (admin only)."""
    user = db["users"].find_one({"username": username})
    if not user:
        return jsonify({"error": "Пользователь не найден"}), 404
    
    user["_id"] = str(user["_id"])
    user.pop("password_hash", None)
    if isinstance(user.get("created_at"), datetime):
        user["created_at"] = user["created_at"].strftime("%Y-%m-%d %H:%M")
    
    return jsonify({"user": user})


@app.route("/api/users/<username>", methods=["PUT"])
@login_required
@admin_required
def update_user(username):
    """Update user information (admin only)."""
    try:
        user = db["users"].find_one({"username": username})
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        data = request.get_json()
        update_data = {}
        
        if "full_name" in data:
            update_data["full_name"] = data.get("full_name", "").strip()
        if "email" in data:
            update_data["email"] = data.get("email", "").strip()
        if "is_active" in data:
            update_data["is_active"] = bool(data.get("is_active"))
        
        if not update_data:
            return jsonify({"error": "Нет данных для обновления"}), 400
        
        result = db["users"].update_one(
            {"username": username},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        return jsonify({"success": True, "message": "Пользователь обновлен"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/users/<username>", methods=["DELETE"])
@login_required
@admin_required
def delete_user(username):
    """Deactivate user (admin only)."""
    try:
        if username == ADMIN_USERNAME:
            return jsonify({"error": "Нельзя деактивировать администратора"}), 400
        
        result = db["users"].update_one(
            {"username": username},
            {"$set": {"is_active": False}}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        return jsonify({"success": True, "message": "Пользователь деактивирован"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/users/<username>/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_user_password(username):
    """Reset user password (admin only)."""
    try:
        data = request.get_json()
        new_password = data.get("password", "")
        
        if not new_password:
            return jsonify({"error": "Новый пароль обязателен"}), 400
        
        user = db["users"].find_one({"username": username})
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        # Hash new password
        password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        
        result = db["users"].update_one(
            {"username": username},
            {"$set": {"password_hash": password_hash}}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        return jsonify({"success": True, "message": "Пароль изменен"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# API endpoints for sharing pets
@app.route("/api/pets/<pet_id>/share", methods=["POST"])
@login_required
def share_pet(pet_id):
    """Share pet with another user (owner only)."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Only owner can share
        if pet.get("owner") != username:
            return jsonify({"error": "Только владелец может делиться животным"}), 403
        
        data = request.get_json()
        share_username = data.get("username", "").strip()
        
        if not share_username:
            return jsonify({"error": "Имя пользователя обязательно"}), 400
        
        # Check if user exists
        user = db["users"].find_one({"username": share_username, "is_active": True})
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        # Don't share with owner
        if share_username == username:
            return jsonify({"error": "Нельзя поделиться с самим собой"}), 400
        
        # Check if already shared
        shared_with = pet.get("shared_with", [])
        if share_username in shared_with:
            return jsonify({"error": "Доступ уже предоставлен этому пользователю"}), 400
        
        # Add to shared_with
        db["pets"].update_one(
            {"_id": ObjectId(pet_id)},
            {"$addToSet": {"shared_with": share_username}}
        )
        
        return jsonify({"success": True, "message": f"Доступ предоставлен пользователю {share_username}"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pets/<pet_id>/share/<share_username>", methods=["DELETE"])
@login_required
def unshare_pet(pet_id, share_username):
    """Remove access from user (owner only)."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Only owner can unshare
        if pet.get("owner") != username:
            return jsonify({"error": "Только владелец может убрать доступ"}), 403
        
        # Remove from shared_with
        db["pets"].update_one(
            {"_id": ObjectId(pet_id)},
            {"$pull": {"shared_with": share_username}}
        )
        
        return jsonify({"success": True, "message": f"Доступ убран у пользователя {share_username}"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pets/<pet_id>/request-access", methods=["POST"])
@login_required
def request_pet_access(pet_id):
    """Request access to pet."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Check if already has access
        if check_pet_access(pet_id, username):
            return jsonify({"error": "У вас уже есть доступ к этому животному"}), 400
        
        # Check if already requested
        access_requests = pet.get("access_requests", [])
        if any(req.get("username") == username for req in access_requests):
            return jsonify({"error": "Запрос на доступ уже отправлен"}), 400
        
        # Add request
        db["pets"].update_one(
            {"_id": ObjectId(pet_id)},
            {"$addToSet": {"access_requests": {
                "username": username,
                "requested_at": datetime.utcnow()
            }}}
        )
        
        return jsonify({"success": True, "message": "Запрос на доступ отправлен"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pets/<pet_id>/access-requests", methods=["GET"])
@login_required
def get_access_requests(pet_id):
    """Get access requests for pet (owner only)."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Only owner can see requests
        if pet.get("owner") != username:
            return jsonify({"error": "Только владелец может просматривать запросы"}), 403
        
        requests = pet.get("access_requests", [])
        for req in requests:
            if isinstance(req.get("requested_at"), datetime):
                req["requested_at"] = req["requested_at"].strftime("%Y-%m-%d %H:%M")
        
        return jsonify({"requests": requests})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pets/<pet_id>/access-requests/<request_username>/approve", methods=["POST"])
@login_required
def approve_access_request(pet_id, request_username):
    """Approve access request (owner only)."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Only owner can approve
        if pet.get("owner") != username:
            return jsonify({"error": "Только владелец может одобрять запросы"}), 403
        
        # Check if request exists
        access_requests = pet.get("access_requests", [])
        if not any(req.get("username") == request_username for req in access_requests):
            return jsonify({"error": "Запрос не найден"}), 404
        
        # Add to shared_with and remove from requests
        db["pets"].update_one(
            {"_id": ObjectId(pet_id)},
            {
                "$addToSet": {"shared_with": request_username},
                "$pull": {"access_requests": {"username": request_username}}
            }
        )
        
        return jsonify({"success": True, "message": f"Доступ предоставлен пользователю {request_username}"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pets/<pet_id>/access-requests/<request_username>/reject", methods=["POST"])
@login_required
def reject_access_request(pet_id, request_username):
    """Reject access request (owner only)."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Only owner can reject
        if pet.get("owner") != username:
            return jsonify({"error": "Только владелец может отклонять запросы"}), 403
        
        # Remove from requests
        db["pets"].update_one(
            {"_id": ObjectId(pet_id)},
            {"$pull": {"access_requests": {"username": request_username}}}
        )
        
        return jsonify({"success": True, "message": f"Запрос отклонен"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pets/<pet_id>", methods=["DELETE"])
@login_required
def delete_pet(pet_id):
    """Delete pet."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Only owner can delete
        if pet.get("owner") != username:
            return jsonify({"error": "Только владелец может удалить животное"}), 403
        
        result = db["pets"].delete_one({"_id": ObjectId(pet_id)})
        
        if result.deleted_count == 0:
            return jsonify({"error": "Животное не найдено"}), 404
        
        return jsonify({"success": True, "message": "Животное удалено"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/asthma", methods=["POST"])
@login_required
def add_asthma_attack():
    """Add asthma attack event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")
        
        if not pet_id:
            return jsonify({"error": "pet_id обязателен"}), 400
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        attack_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "duration": data.get("duration", ""),
            "reason": data.get("reason", ""),
            "inhalation": data.get("inhalation", False),
            "comment": data.get("comment", "")
        }
        
        db["asthma_attacks"].insert_one(attack_data)
        return jsonify({"success": True, "message": "Приступ астмы записан"}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/defecation", methods=["POST"])
@login_required
def add_defecation():
    """Add defecation event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")
        
        if not pet_id:
            return jsonify({"error": "pet_id обязателен"}), 400
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        defecation_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "stool_type": data.get("stool_type", ""),
            "color": data.get("color", "Коричневый"),
            "food": data.get("food", ""),
            "comment": data.get("comment", "")
        }
        
        db["defecations"].insert_one(defecation_data)
        return jsonify({"success": True, "message": "Дефекация записана"}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/litter", methods=["POST"])
@login_required
def add_litter():
    """Add litter change event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")
        
        if not pet_id:
            return jsonify({"error": "pet_id обязателен"}), 400
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        litter_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "comment": data.get("comment", "")
        }
        
        db["litter_changes"].insert_one(litter_data)
        return jsonify({"success": True, "message": "Смена лотка записана"}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/weight", methods=["POST"])
@login_required
def add_weight():
    """Add weight measurement."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")
        
        if not pet_id:
            return jsonify({"error": "pet_id обязателен"}), 400
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        weight_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "weight": data.get("weight", ""),
            "food": data.get("food", ""),
            "comment": data.get("comment", "")
        }
        
        db["weights"].insert_one(weight_data)
        return jsonify({"success": True, "message": "Вес записан"}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/asthma", methods=["GET"])
@login_required
def get_asthma_attacks():
    """Get asthma attacks for current pet."""
    pet_id = request.args.get("pet_id")
    
    if not pet_id:
        return jsonify({"error": "pet_id обязателен"}), 400
    
    username = getattr(request, 'current_user', None)
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Check pet access
    if not check_pet_access(pet_id, username):
        return jsonify({"error": "Нет доступа к этому животному"}), 403
    
    attacks = list(db["asthma_attacks"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))
    
    for attack in attacks:
        attack["_id"] = str(attack["_id"])
        if isinstance(attack.get("date_time"), datetime):
            attack["date_time"] = attack["date_time"].strftime("%Y-%m-%d %H:%M")
        if attack.get("inhalation") is True:
            attack["inhalation"] = "Да"
        elif attack.get("inhalation") is False:
            attack["inhalation"] = "Нет"
    
    return jsonify({"attacks": attacks})


@app.route("/api/defecation", methods=["GET"])
@login_required
def get_defecations():
    """Get defecations for current pet."""
    pet_id = request.args.get("pet_id")
    
    if not pet_id:
        return jsonify({"error": "pet_id обязателен"}), 400
    
    username = getattr(request, 'current_user', None)
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Check pet access
    if not check_pet_access(pet_id, username):
        return jsonify({"error": "Нет доступа к этому животному"}), 403
    
    defecations = list(db["defecations"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))
    
    for defecation in defecations:
        defecation["_id"] = str(defecation["_id"])
        if isinstance(defecation.get("date_time"), datetime):
            defecation["date_time"] = defecation["date_time"].strftime("%Y-%m-%d %H:%M")
    
    return jsonify({"defecations": defecations})


@app.route("/api/litter", methods=["GET"])
@login_required
def get_litter_changes():
    """Get litter changes for current pet."""
    pet_id = request.args.get("pet_id")
    
    if not pet_id:
        return jsonify({"error": "pet_id обязателен"}), 400
    
    username = getattr(request, 'current_user', None)
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Check pet access
    if not check_pet_access(pet_id, username):
        return jsonify({"error": "Нет доступа к этому животному"}), 403
    
    litter_changes = list(db["litter_changes"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))
    
    for change in litter_changes:
        change["_id"] = str(change["_id"])
        if isinstance(change.get("date_time"), datetime):
            change["date_time"] = change["date_time"].strftime("%Y-%m-%d %H:%M")
    
    return jsonify({"litter_changes": litter_changes})


@app.route("/api/weight", methods=["GET"])
@login_required
def get_weights():
    """Get weight measurements for current pet."""
    pet_id = request.args.get("pet_id")
    
    if not pet_id:
        return jsonify({"error": "pet_id обязателен"}), 400
    
    username = getattr(request, 'current_user', None)
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Check pet access
    if not check_pet_access(pet_id, username):
        return jsonify({"error": "Нет доступа к этому животному"}), 403
    
    weights = list(db["weights"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))
    
    for weight in weights:
        weight["_id"] = str(weight["_id"])
        if isinstance(weight.get("date_time"), datetime):
            weight["date_time"] = weight["date_time"].strftime("%Y-%m-%d %H:%M")
    
    return jsonify({"weights": weights})


@app.route("/api/asthma/<record_id>", methods=["PUT"])
@login_required
def update_asthma_attack(record_id):
    """Update asthma attack event."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["asthma_attacks"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        data = request.get_json()
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        attack_data = {
            "date_time": event_dt,
            "duration": data.get("duration", ""),
            "reason": data.get("reason", ""),
            "inhalation": data.get("inhalation", False),
            "comment": data.get("comment", "")
        }
        
        result = db["asthma_attacks"].update_one(
            {"_id": ObjectId(record_id)},
            {"$set": attack_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Приступ астмы обновлен"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/asthma/<record_id>", methods=["DELETE"])
@login_required
def delete_asthma_attack(record_id):
    """Delete asthma attack event."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["asthma_attacks"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        result = db["asthma_attacks"].delete_one(
            {"_id": ObjectId(record_id)}
        )
        
        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Приступ астмы удален"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/defecation/<record_id>", methods=["PUT"])
@login_required
def update_defecation(record_id):
    """Update defecation event."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["defecations"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        data = request.get_json()
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        defecation_data = {
            "date_time": event_dt,
            "stool_type": data.get("stool_type", ""),
            "color": data.get("color", "Коричневый"),
            "food": data.get("food", ""),
            "comment": data.get("comment", "")
        }
        
        result = db["defecations"].update_one(
            {"_id": ObjectId(record_id)},
            {"$set": defecation_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Дефекация обновлена"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/defecation/<record_id>", methods=["DELETE"])
@login_required
def delete_defecation(record_id):
    """Delete defecation event."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["defecations"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        result = db["defecations"].delete_one(
            {"_id": ObjectId(record_id)}
        )
        
        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Дефекация удалена"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/litter/<record_id>", methods=["PUT"])
@login_required
def update_litter(record_id):
    """Update litter change event."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["litter_changes"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        data = request.get_json()
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        litter_data = {
            "date_time": event_dt,
            "comment": data.get("comment", "")
        }
        
        result = db["litter_changes"].update_one(
            {"_id": ObjectId(record_id)},
            {"$set": litter_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Смена лотка обновлена"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/litter/<record_id>", methods=["DELETE"])
@login_required
def delete_litter(record_id):
    """Delete litter change event."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["litter_changes"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        result = db["litter_changes"].delete_one(
            {"_id": ObjectId(record_id)}
        )
        
        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Смена лотка удалена"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/weight/<record_id>", methods=["PUT"])
@login_required
def update_weight(record_id):
    """Update weight measurement."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["weights"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        data = request.get_json()
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        weight_data = {
            "date_time": event_dt,
            "weight": data.get("weight", ""),
            "food": data.get("food", ""),
            "comment": data.get("comment", "")
        }
        
        result = db["weights"].update_one(
            {"_id": ObjectId(record_id)},
            {"$set": weight_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Вес обновлен"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/weight/<record_id>", methods=["DELETE"])
@login_required
def delete_weight(record_id):
    """Delete weight measurement."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["weights"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        result = db["weights"].delete_one(
            {"_id": ObjectId(record_id)}
        )
        
        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Вес удален"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/feeding", methods=["POST"])
@login_required
def add_feeding():
    """Add feeding event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")
        
        if not pet_id:
            return jsonify({"error": "pet_id обязателен"}), 400
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        feeding_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "food_weight": data.get("food_weight", ""),
            "comment": data.get("comment", "")
        }
        
        db["feedings"].insert_one(feeding_data)
        return jsonify({"success": True, "message": "Дневная порция записана"}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/feeding", methods=["GET"])
@login_required
def get_feedings():
    """Get feedings for current pet."""
    pet_id = request.args.get("pet_id")
    
    if not pet_id:
        return jsonify({"error": "pet_id обязателен"}), 400
    
    username = getattr(request, 'current_user', None)
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Check pet access
    if not check_pet_access(pet_id, username):
        return jsonify({"error": "Нет доступа к этому животному"}), 403
    
    feedings = list(db["feedings"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))
    
    for feeding in feedings:
        feeding["_id"] = str(feeding["_id"])
        if isinstance(feeding.get("date_time"), datetime):
            feeding["date_time"] = feeding["date_time"].strftime("%Y-%m-%d %H:%M")
    
    return jsonify({"feedings": feedings})


@app.route("/api/feeding/<record_id>", methods=["PUT"])
@login_required
def update_feeding(record_id):
    """Update feeding event."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["feedings"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        data = request.get_json()
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        feeding_data = {
            "date_time": event_dt,
            "food_weight": data.get("food_weight", ""),
            "comment": data.get("comment", "")
        }
        
        result = db["feedings"].update_one(
            {"_id": ObjectId(record_id)},
            {"$set": feeding_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Дневная порция обновлена"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/feeding/<record_id>", methods=["DELETE"])
@login_required
def delete_feeding(record_id):
    """Delete feeding event."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Get existing record to check pet_id
        existing = db["feedings"].find_one({"_id": ObjectId(record_id)})
        if not existing:
            return jsonify({"error": "Record not found"}), 404
        
        pet_id = existing.get("pet_id")
        if not pet_id:
            return jsonify({"error": "Invalid record"}), 400
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        result = db["feedings"].delete_one(
            {"_id": ObjectId(record_id)}
        )
        
        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Дневная порция удалена"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/export/<export_type>/<format_type>", methods=["GET"])
@login_required
def export_data(export_type, format_type):
    """Export data in various formats."""
    try:
        pet_id = request.args.get("pet_id")
        
        if not pet_id:
            return jsonify({"error": "pet_id обязателен"}), 400
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403
        
        if export_type == "feeding":
            collection = db["feedings"]
            title = "Дневные порции корма"
            fields = [
                ("date_time", "Дата и время"),
                ("food_weight", "Вес корма (г)"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "asthma":
            collection = db["asthma_attacks"]
            title = "Приступы астмы"
            fields = [
                ("date_time", "Дата и время"),
                ("duration", "Длительность"),
                ("reason", "Причина"),
                ("inhalation", "Ингаляция"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "defecation":
            collection = db["defecations"]
            title = "Дефекации"
            fields = [
                ("date_time", "Дата и время"),
                ("stool_type", "Тип стула"),
                ("color", "Цвет стула"),
                ("food", "Корм"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "litter":
            collection = db["litter_changes"]
            title = "Смена лотка"
            fields = [
                ("date_time", "Дата и время"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "weight":
            collection = db["weights"]
            title = "Вес"
            fields = [
                ("date_time", "Дата и время"),
                ("weight", "Вес (кг)"),
                ("food", "Корм"),
                ("comment", "Комментарий"),
            ]
        else:
            return jsonify({"error": "Invalid export type"}), 400
        
        records = list(collection.find({"pet_id": pet_id}).sort([("date_time", -1)]))
        
        if not records:
            return jsonify({"error": "Нет данных для выгрузки"}), 404
        
        # Prepare records
        for r in records:
            if isinstance(r.get("date_time"), datetime):
                r["date_time"] = r["date_time"].strftime("%Y-%m-%d %H:%M")
            else:
                r["date_time"] = str(r.get("date_time", ""))
            
            if r.get("comment", "").strip() in ("", "Пропустить"):
                r["comment"] = "-"
            
            if r.get("food", "").strip() in ("", "Пропустить"):
                r["food"] = "-"
            
            if export_type == "asthma":
                inh = r.get("inhalation")
                if inh is True:
                    r["inhalation"] = "Да"
                elif inh is False:
                    r["inhalation"] = "Нет"
                else:
                    r["inhalation"] = "-"
        
        # Generate file based on format
        filename_base = f"{title.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        if format_type == "csv":
            output = io.StringIO()
            fieldnames = [ru for _, ru in fields]
            writer = csv.writer(output)
            writer.writerow(fieldnames)
            for r in records:
                writer.writerow([str(r.get(en, "") or "") for en, _ in fields])
            content = output.getvalue().encode("utf-8-sig")  # BOM for Excel
            mimetype = "text/csv"
            filename = f"{filename_base}.csv"
            
        elif format_type == "tsv":
            output = io.StringIO()
            fieldnames = [ru for _, ru in fields]
            writer = csv.writer(output, delimiter="\t")
            writer.writerow(fieldnames)
            for r in records:
                writer.writerow([str(r.get(en, "") or "") for en, _ in fields])
            content = output.getvalue().encode("utf-8")
            mimetype = "text/tab-separated-values"
            filename = f"{filename_base}.tsv"
            
        elif format_type == "html":
            html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #000; color: #fff; }}
        table {{ width: 100%; border-collapse: collapse; background: #1c1c1e; border-radius: 10px; overflow: hidden; }}
        th {{ background: #2c2c2e; padding: 12px; text-align: left; font-weight: 600; border-bottom: 1px solid #38383a; }}
        td {{ padding: 12px; border-bottom: 1px solid #38383a; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover {{ background: #2c2c2e; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <table>
        <thead>
            <tr>
"""
            for _, ru in fields:
                html += f"                <th>{ru}</th>\n"
            html += """            </tr>
        </thead>
        <tbody>
"""
            for r in records:
                html += "            <tr>\n"
                for en, _ in fields:
                    value = str(r.get(en, "") or "").replace("<", "&lt;").replace(">", "&gt;")
                    html += f"                <td>{value}</td>\n"
                html += "            </tr>\n"
            html += """        </tbody>
    </table>
</body>
</html>"""
            content = html.encode("utf-8")
            mimetype = "text/html"
            filename = f"{filename_base}.html"
            
        elif format_type == "md":
            md = f"# {title}\n\n"
            md += "| " + " | ".join(ru for _, ru in fields) + " |\n"
            md += "|" + "---|" * len(fields) + "\n"
            for r in records:
                md += "| " + " | ".join(str(r.get(en, "") or "").replace("|", "\\|") for en, _ in fields) + " |\n"
            content = md.encode("utf-8")
            mimetype = "text/markdown"
            filename = f"{filename_base}.md"
            
        else:
            return jsonify({"error": "Invalid format type"}), 400
        
        # Encode filename for HTTP header (RFC 5987)
        encoded_filename = quote(filename)
        
        response = make_response(content)
        response.headers["Content-Type"] = mimetype
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        return response
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pets/<pet_id>/photo", methods=["GET"])
@login_required
def get_pet_photo(pet_id):
    """Get pet photo file."""
    try:
        from bson import ObjectId
        
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401
        
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return jsonify({"error": "Животное не найдено"}), 404
        
        # Check access
        if pet.get("owner") != username and username not in pet.get("shared_with", []):
            return jsonify({"error": "Нет доступа"}), 403
        
        photo_file_id = pet.get("photo_file_id")
        if not photo_file_id:
            return jsonify({"error": "Фото не найдено"}), 404
        
        try:
            photo_file = fs.get(ObjectId(photo_file_id))
            photo_data = photo_file.read()
            
            response = make_response(photo_data)
            response.headers.set('Content-Type', photo_file.content_type)
            response.headers.set('Content-Disposition', 'inline')
            response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
            response.headers.set('Pragma', 'no-cache')
            response.headers.set('Expires', '0')
            return response
        except Exception as e:
            return jsonify({"error": "Ошибка загрузки фото"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    ensure_default_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)

