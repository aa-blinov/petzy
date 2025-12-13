"""Flask web application for cat health tracking."""

import csv
import io
import os
import time
from datetime import datetime
from functools import wraps
from urllib.parse import quote

import bcrypt
from flask import Flask, jsonify, make_response, redirect, render_template, request, session, url_for

from web.db import db

# Configure Flask app with proper template and static folders
app = Flask(
    __name__,
    template_folder='templates',
    static_folder='static'
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

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

# Rate limiting for login attempts
login_attempts = {}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_TIME = 300  # 5 minutes in seconds


def login_required(f):
    """Decorator to require login for routes."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            # For API routes, return JSON error instead of redirect
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def index():
    """Redirect to login or dashboard."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page with rate limiting and password hashing."""
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
                return render_template("login.html", error=f"Слишком много попыток. Попробуйте через {remaining_time} мин.")
            elif attempts_data["count"] >= MAX_LOGIN_ATTEMPTS:
                # Reset after lockout period
                if time.time() - attempts_data["last_attempt"] > LOGIN_LOCKOUT_TIME:
                    login_attempts[client_ip] = {"count": 0, "last_attempt": time.time(), "locked_until": 0}
                else:
                    remaining_time = int((attempts_data["locked_until"] - time.time()) / 60) + 1
                    return render_template("login.html", error=f"Слишком много попыток. Попробуйте через {remaining_time} мин.")
        
        # Verify username and password
        if username == ADMIN_USERNAME:
            try:
                # Verify password using bcrypt
                if bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH.encode()):
                    # Successful login - reset attempts
                    if client_ip in login_attempts:
                        del login_attempts[client_ip]
                    
                    session["user_id"] = "admin"
                    session["username"] = username
                    session["db_user_id"] = DEFAULT_USER_ID
                    return redirect(url_for("dashboard"))
            except (ValueError, TypeError):
                # Invalid hash format
                pass
        
        # Failed login - increment attempts
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
    """Logout and clear session."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard page."""
    return render_template("dashboard.html", username=session.get("username", ""))


@app.route("/api/asthma", methods=["POST"])
@login_required
def add_asthma_attack():
    """Add asthma attack event."""
    try:
        data = request.get_json()
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        attack_data = {
            "user_id": user_id,
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
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        defecation_data = {
            "user_id": user_id,
            "date_time": event_dt,
            "stool_type": data.get("stool_type", ""),
            "food": data.get("food", ""),
            "comment": data.get("comment", "")
        }
        
        db["defecations"].insert_one(defecation_data)
        return jsonify({"success": True, "message": "Дефекация записана"}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/weight", methods=["POST"])
@login_required
def add_weight():
    """Add weight measurement."""
    try:
        data = request.get_json()
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        if date_str and time_str:
            event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            event_dt = datetime.now()
        
        weight_data = {
            "user_id": user_id,
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
    """Get asthma attacks for current user."""
    user_id = session.get("db_user_id", DEFAULT_USER_ID)
    
    attacks = list(db["asthma_attacks"].find({"user_id": user_id}).sort("date_time", -1).limit(100))
    
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
    """Get defecations for current user."""
    user_id = session.get("db_user_id", DEFAULT_USER_ID)
    
    defecations = list(db["defecations"].find({"user_id": user_id}).sort("date_time", -1).limit(100))
    
    for defecation in defecations:
        defecation["_id"] = str(defecation["_id"])
        if isinstance(defecation.get("date_time"), datetime):
            defecation["date_time"] = defecation["date_time"].strftime("%Y-%m-%d %H:%M")
    
    return jsonify({"defecations": defecations})


@app.route("/api/weight", methods=["GET"])
@login_required
def get_weights():
    """Get weight measurements for current user."""
    user_id = session.get("db_user_id", DEFAULT_USER_ID)
    
    weights = list(db["weights"].find({"user_id": user_id}).sort("date_time", -1).limit(100))
    
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
        
        data = request.get_json()
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
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
            {"_id": ObjectId(record_id), "user_id": user_id},
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
        
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
        result = db["asthma_attacks"].delete_one(
            {"_id": ObjectId(record_id), "user_id": user_id}
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
        
        data = request.get_json()
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
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
            "food": data.get("food", ""),
            "comment": data.get("comment", "")
        }
        
        result = db["defecations"].update_one(
            {"_id": ObjectId(record_id), "user_id": user_id},
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
        
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
        result = db["defecations"].delete_one(
            {"_id": ObjectId(record_id), "user_id": user_id}
        )
        
        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Дефекация удалена"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/weight/<record_id>", methods=["PUT"])
@login_required
def update_weight(record_id):
    """Update weight measurement."""
    try:
        from bson import ObjectId
        
        data = request.get_json()
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
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
            {"_id": ObjectId(record_id), "user_id": user_id},
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
        
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
        result = db["weights"].delete_one(
            {"_id": ObjectId(record_id), "user_id": user_id}
        )
        
        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404
        
        return jsonify({"success": True, "message": "Вес удален"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/export/<export_type>/<format_type>", methods=["GET"])
@login_required
def export_data(export_type, format_type):
    """Export data in various formats."""
    try:
        user_id = session.get("db_user_id", DEFAULT_USER_ID)
        
        if export_type == "asthma":
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
                ("food", "Корм"),
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
        
        records = list(collection.find({"user_id": user_id}).sort([("date_time", -1)]))
        
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

