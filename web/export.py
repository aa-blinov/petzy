"""Data export routes (CSV/TSV/HTML/Markdown) for health records."""

import csv
import io
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, jsonify, make_response, request
from flask_pydantic_spec import Response

import web.app as app  # access db, logger
from web.app import api
from web.security import login_required
from web.helpers import check_pet_access
from web.schemas import ErrorResponse, PetIdQuery


export_bp = Blueprint("export", __name__)


@export_bp.route("/api/export/<export_type>/<format_type>", methods=["GET"])
@login_required
@api.validate(
    query=PetIdQuery,
    resp=Response(
        HTTP_200=None, HTTP_422=ErrorResponse, HTTP_401=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse
    ),
    tags=["export"],
)
def export_data(export_type, format_type):
    """Export data in various formats."""
    try:
        pet_id = request.context.query.pet_id

        username = getattr(request, "current_user", None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401

        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403

        if export_type == "feeding":
            collection = app.db["feedings"]
            title = "Дневные порции корма"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("food_weight", "Вес корма (г)"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "asthma":
            collection = app.db["asthma_attacks"]
            title = "Приступы астмы"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("duration", "Длительность"),
                ("reason", "Причина"),
                ("inhalation", "Ингаляция"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "defecation":
            collection = app.db["defecations"]
            title = "Дефекации"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("stool_type", "Тип стула"),
                ("color", "Цвет стула"),
                ("food", "Корм"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "litter":
            collection = app.db["litter_changes"]
            title = "Смена лотка"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "weight":
            collection = app.db["weights"]
            title = "Вес"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("weight", "Вес (кг)"),
                ("food", "Корм"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "eye-drops":
            collection = app.db["eye_drops"]
            title = "Закапывание глаз"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("drops_type", "Тип капель"),
                ("comment", "Комментарий"),
            ]
        else:
            return jsonify({"error": "Invalid export type"}), 422

        records = list(collection.find({"pet_id": pet_id}).sort([("date_time", -1)]))

        if not records:
            return jsonify({"error": "Нет данных для выгрузки"}), 404

        # Prepare records
        for r in records:
            if isinstance(r.get("date_time"), datetime):
                r["date_time"] = r["date_time"].strftime("%d.%m.%Y %H:%M")
            else:
                r["date_time"] = str(r.get("date_time", ""))

            if not r.get("username"):
                r["username"] = "-"

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
            content = output.getvalue().encode("utf-8-sig")
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
            md = f"# {title}\\n\\n"
            md += "| " + " | ".join(ru for _, ru in fields) + " |\\n"
            md += "|" + "---|" * len(fields) + "\\n"
            for r in records:
                md += "| " + " | ".join(str(r.get(en, "") or "").replace("|", "\\\\|") for en, _ in fields) + " |\\n"
            content = md.encode("utf-8")
            mimetype = "text/markdown"
            filename = f"{filename_base}.md"

        else:
            return jsonify({"error": "Invalid format type"}), 422

        encoded_filename = quote(filename)

        response = make_response(content)
        response.headers["Content-Type"] = mimetype
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        app.logger.info(f"Data exported: type={export_type}, format={format_type}, pet_id={pet_id}, user={username}")
        return response

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for export: type={export_type}, format={format_type}, pet_id={pet_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 422
