"""The life history (анамнез жизни) as a PDF (A4), for a vet.

The medical card's PDF is a summary; this one is the whole record, in the
order a history is read: who the animal is and what a vet must know first,
then everything that has happened to it from its birth on, year by year,
its medication courses, the weight curve, what the diary holds, and the
documents. Drawn with the card's own pieces (``web.medical_card_pdf``).
"""

from datetime import datetime

from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from web.medical_card_pdf import (
    ALERT,
    AMBER,
    BAND,
    INK,
    LINE,
    MUTED,
    TARGET_LABELS,
    _Card,
    _date,
    _number,
    draw_course,
    draw_header,
)

KIND_LABELS = {
    "vaccination": "Прививка",
    "parasite": "Обработка от паразитов",
    "visit": "Визит к врачу",
    "procedure": "Операция или процедура",
}
DOCUMENT_CATEGORIES = {
    "vaccination": "Прививки",
    "lab_result": "Анализ",
    "conclusion": "Заключение",
    "imaging": "Снимок",
    "insurance": "Страховка",
    "other": "Другое",
}
ACCENT = (196, 106, 63)
COLUMNS = (24, 42, 114)
WEIGHT_TABLE_PAIRS = 3


def _record_details(r: dict) -> str:
    """The lines under a record's title in the timeline."""
    lines = [r["title"] + (f" (серия {r['batch']})" if r.get("batch") else "")]
    if r.get("target"):
        lines.append(TARGET_LABELS.get(r["target"], r["target"]).capitalize())
    if r["kind"] in ("vaccination", "parasite") and r.get("next_due") and not r["superseded"]:
        lines.append(f"Следующая: {_date(r['next_due'])}")
    elif r.get("next_due") and r["kind"] not in ("vaccination", "parasite"):
        lines.append(f"Повторно: {_date(r['next_due'])}")
    where = ", ".join(x for x in (r.get("clinic"), f"врач {r['vet']}" if r.get("vet") else None) if x)
    if where:
        lines.append(where)
    for label, key in (("Диагноз", "diagnosis"), ("Рекомендации", "recommendations"), ("Заметка", "note")):
        if r.get(key):
            lines.append(f"{label}: {r[key]}")
    if r.get("documents"):
        lines.append("Документы: " + ", ".join(d["title"] for d in r["documents"]))
    return "\n".join(lines)


def _timeline(card: dict) -> list[dict]:
    """Everything dated, oldest first: the birth, the records, the certificates kept only as documents."""
    rows = []
    if card["pet"].get("birth_date"):
        rows.append(
            {"date": card["pet"]["birth_date"], "what": "Рождение", "details": card["pet"].get("age_text") or ""}
        )
    for r in card["timeline_records"]:
        rows.append({"date": r["date"], "what": KIND_LABELS.get(r["kind"], r["kind"]), "details": _record_details(r)})
    added = {d["id"]: d["added"] for d in card["documents"]}
    for v in card["vaccinations"]:
        if not added.get(v["id"]):
            continue
        until = f"\nДействует до {_date(v['expires_at'])}" if v.get("expires_at") else ""
        rows.append({"date": added[v["id"]], "what": "Прививка (сертификат)", "details": f"{v['title']}{until}"})
    rows.sort(key=lambda row: row["date"])
    return rows


def _section_table(pdf: _Card, rows: list[dict]) -> None:
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(*INK)
    pdf.set_fill_color(255, 255, 255)  # the header boxes left their tint set; only the year rows are tinted
    year_style = FontFace(emphasis="BOLD", color=ALERT, fill_color=BAND)
    with pdf.table(
        col_widths=COLUMNS,
        text_align=("LEFT", "LEFT", "LEFT"),
        line_height=5,
        borders_layout="HORIZONTAL_LINES",
        first_row_as_headings=False,
        padding=1.2,
    ) as table:
        year = None
        for row in rows:
            if row["date"][:4] != year:
                year = row["date"][:4]
                table.row().cell(year, colspan=3, style=year_style)
            table.row([_date(row["date"]), row["what"], row["details"]])


def _weight_chart(pdf: _Card, series: list[dict]) -> None:
    """The weight over time: a line on a frame, the range and the first and last date named."""
    height = 38
    if pdf.get_y() + height + 14 > pdf.h - 20:
        pdf.add_page()
    left, width = pdf.l_margin + 14, pdf.w - pdf.l_margin - pdf.r_margin - 14
    top = pdf.get_y() + 2
    values = [p["value"] for p in series]
    low, high = min(values), max(values)
    span = (high - low) or 1
    days = [datetime.strptime(p["date"], "%Y-%m-%d").toordinal() for p in series]
    first, last_day = days[0], days[-1]
    total = (last_day - first) or 1

    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.2)
    pdf.rect(left, top, width, height)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.set_xy(pdf.l_margin, top - 1)
    pdf.cell(13, 4, f"{_number(high)}", align="R")
    pdf.set_xy(pdf.l_margin, top + height - 3)
    pdf.cell(13, 4, f"{_number(low)}", align="R")

    points = [
        (left + 2 + (d - first) / total * (width - 4), top + height - 3 - (v - low) / span * (height - 6))
        for d, v in zip(days, values)
    ]
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.6)
    if len(points) > 1:
        pdf.polyline(points)
    pdf.set_fill_color(*ACCENT)
    x, y = points[-1]
    pdf.ellipse(x - 1, y - 1, 2, 2, style="F")
    pdf.set_line_width(0.2)

    pdf.set_xy(left, top + height + 1)
    pdf.cell(width / 2, 4, _date(series[0]["date"]), align="L")
    pdf.cell(width / 2, 4, _date(series[-1]["date"]), align="R")
    pdf.set_y(top + height + 7)


def _weight_section(pdf: _Card, weight: dict | None) -> None:
    pdf.section("Вес")
    if not weight:
        pdf.muted("Замеров нет.")
        return
    series = weight["series"]
    first, last = series[0], series[-1]
    lowest = min(series, key=lambda p: p["value"])
    highest = max(series, key=lambda p: p["value"])
    pdf.row(f"Последний замер: {_number(last['value'])} кг", _date(last["date"]), bold_left=True)
    if len(series) > 1:
        change = last["value"] - first["value"]
        sign = "+" if change > 0 else ""
        pdf.muted(
            f"Первый замер: {_number(first['value'])} кг ({_date(first['date'])}). Изменение: {sign}{_number(round(change, 2))} кг."
        )
        pdf.muted(
            f"Наименьший: {_number(lowest['value'])} кг ({_date(lowest['date'])}), "
            f"наибольший: {_number(highest['value'])} кг ({_date(highest['date'])}). Замеров: {len(series)}."
        )
        _weight_chart(pdf, series)
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*INK)
        pdf.set_fill_color(255, 255, 255)  # the chart's dot left its colour set, and a table fills its cells with it
        with pdf.table(
            col_widths=(24, 18) * WEIGHT_TABLE_PAIRS,
            text_align=("LEFT", "RIGHT") * WEIGHT_TABLE_PAIRS,
            line_height=4.5,
            borders_layout="NONE",
            first_row_as_headings=False,
            padding=0.6,
        ) as table:
            for i in range(0, len(series), WEIGHT_TABLE_PAIRS):
                cells = []
                for p in series[i : i + WEIGHT_TABLE_PAIRS]:
                    cells += [_date(p["date"]), f"{_number(p['value'])} кг"]
                table.row(cells + [""] * (WEIGHT_TABLE_PAIRS * 2 - len(cells)))


def _events_section(pdf: _Card, summary: list[dict]) -> None:
    pdf.section("Записи из дневника")
    if not summary:
        pdf.muted("Записей нет.")
        return
    for row in summary:
        if pdf.get_y() > pdf.h - 38:  # a title and its line of numbers stay on one page
            pdf.add_page()
        pdf.row(row["label"], f"всего {row['total']}", bold_left=True)
        years = ", ".join(f"{year}: {count}" for year, count in row["years"].items())
        pdf.muted(f"С {_date(row['first'])} по {_date(row['last'])}. По годам: {years}")
        pdf.ln(1)


def _documents_section(pdf: _Card, documents: list[dict]) -> None:
    pdf.section("Документы")
    if not documents:
        pdf.muted("Документов нет.")
        return
    for d in documents:
        label = DOCUMENT_CATEGORIES.get(d["category"], "Документ") + (
            f", до {_date(d['expires_at'])}" if d.get("expires_at") else ""
        )
        pdf.row(d["title"], f"{label}, добавлен {_date(d['added'])}", MUTED)


def render_anamnesis_pdf(card: dict) -> bytes:
    pet = card["pet"]
    pdf = _Card(pet["name"], card["generated_at"])
    pdf.set_title(f"Анамнез жизни: {pet['name']}")
    pdf.alias_nb_pages()
    pdf.add_page()
    draw_header(pdf, card, "АНАМНЕЗ ЖИЗНИ")

    pdf.section("Хронология")
    rows = _timeline(card)
    if len(rows) > (1 if pet.get("birth_date") else 0):
        _section_table(pdf, rows)
    else:
        pdf.muted("Записей о прививках, обработках, визитах и операциях нет.")

    pdf.section("Курсы препаратов")
    if not card["medications"] and not card["past_courses"]:
        pdf.muted("Курсов нет.")
    if card["medications"]:
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_text_color(*AMBER)
        pdf.cell(0, 6, "Идут сейчас", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for c in card["medications"]:
            draw_course(pdf, c, past=False)
    if card["past_courses"]:
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 6, "Закончены", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for c in card["past_courses"]:
            draw_course(pdf, c, past=True)

    _weight_section(pdf, card.get("weight"))
    _events_section(pdf, card["event_summary"])
    _documents_section(pdf, card["documents"])
    return bytes(pdf.output())
