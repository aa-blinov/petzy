"""The medical card as a PDF (A4), for a vet: one document for the appointment and for the history.

The first page is «now»: who the animal is, allergies and conditions, what is
overdue or soon due, the medicines it takes, its last weight. Everything a vet
asks first, readable on its own. The pages after it are the record from the
birth on: the timeline year by year, every course, the weight curve, what the
diary holds, the documents.

Built with fpdf2 and the DejaVu Sans fonts bundled in ``web/fonts``: the
built-in PDF fonts have no Cyrillic. Plain black on white, meant to be read
on paper or on a phone in a messenger, not to look like the app.
"""

import os
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
MARGIN = 16
INK = (31, 27, 22)
MUTED = (95, 88, 80)
LINE = (210, 203, 190)
ALERT = (179, 38, 30)
AMBER = (154, 88, 0)
BAND = (250, 246, 239)

STATUS_LABELS = {"valid": "Действует", "soon": "Скоро истекает", "expired": "Истекла", "none": "Срок не указан"}
STATUS_COLORS = {"valid": INK, "soon": AMBER, "expired": ALERT, "none": MUTED}
TARGET_LABELS = {"fleas_ticks": "от блох и клещей", "worms": "от глистов", "both": "от блох, клещей и глистов"}


def _date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso


def _period(course: dict, past: bool) -> str:
    """«С 12.05.2026 по 26.05.2026», «С 12.05.2026», «Начнётся 05.10.2026»."""
    started, ended = _date(course.get("started_on")), _date(course.get("ended_on"))
    if course.get("status") == "planned" and started:
        return f"Начнётся {started}"
    if started and ended:
        return f"С {started} по {ended}"
    if started:
        return f"С {started}" if not past else f"С {started}, дата окончания не указана"
    return f"Закончен {ended}" if ended else ""


def _number(value: float) -> str:
    return f"{value:g}".replace(".", ",")


class _Card(FPDF):
    def __init__(self, pet_name: str, generated_at: str):
        super().__init__(format="A4", unit="mm")
        self.pet_name = pet_name
        self.generated_at = generated_at
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(auto=True, margin=18)
        self.add_font("DejaVu", "", os.path.join(FONT_DIR, "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))
        self.set_title(f"Медицинская карта: {pet_name}")
        self.set_creator("Petzy")

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"Petzy, сформировано {_date(self.generated_at)}", align="L")
        self.cell(0, 6, f"Страница {self.page_no()} из {{nb}}", align="R")

    def section(self, title: str):
        self.ln(4)
        self.set_font("DejaVu", "B", 11)
        self.set_text_color(*INK)
        self.cell(0, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LINE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

    def muted(self, text: str):
        self.set_font("DejaVu", "", 9)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 5, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def row(self, left: str, right: str = "", right_color=INK, bold_left: bool = False):
        """One line of a list: text on the left, a short value on the right."""
        width = self.w - self.l_margin - self.r_margin
        right_w = self.get_string_width(right) + 2 if right else 0
        self.set_font("DejaVu", "B" if bold_left else "", 10)
        self.set_text_color(*INK)
        start_y = self.get_y()
        # The text may take several lines; the next row starts below the last.
        self.multi_cell(width - right_w - 2, 6, left, align="L", new_x=XPos.LEFT, new_y=YPos.NEXT)
        end_y = self.get_y()
        if right:
            self.set_xy(self.w - self.r_margin - right_w, start_y)
            self.set_font("DejaVu", "", 10)
            self.set_text_color(*right_color)
            self.cell(right_w, 6, right, align="R")
        # A little air under a row that took several lines.
        self.set_xy(self.l_margin, max(end_y, start_y + 6) + (1 if end_y > start_y + 6 else 0))


def draw_header(pdf: "_Card", card: dict, heading: str) -> None:
    """The top of the first page: name, the facts, identification, clinic, and the box a vet reads first."""
    pet = card["pet"]
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, heading, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "B", 22)
    pdf.set_text_color(*INK)
    pdf.cell(0, 12, pet["name"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    facts = [pet.get("species"), pet.get("breed")]
    if pet.get("birth_date"):
        born = _date(pet["birth_date"])
        facts.append(f"родился {born}" + (f" ({pet['age_text']})" if pet.get("age_text") else ""))
    if pet.get("gender"):
        facts.append(pet["gender"])
    if pet.get("neutered_text"):
        facts.append(pet["neutered_text"])
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0, 6, ", ".join(f for f in facts if f) or "Данные о питомце не заполнены", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )

    profile = card.get("profile") or {}
    ids = []
    if profile.get("blood_type"):
        ids.append(f"Группа крови: {profile['blood_type']}")
    if profile.get("chip_number"):
        ids.append(f"чип {profile['chip_number']}" if ids else f"Чип: {profile['chip_number']}")
    if ids:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 6, ", ".join(ids), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    clinic = profile.get("clinic") or {}
    clinic_bits = [
        clinic.get("name"),
        f"врач {clinic['vet']}" if clinic.get("vet") else None,
        f"тел. {clinic['phone']}" if clinic.get("phone") else None,
    ]
    if any(clinic_bits):
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(
            0, 6, "Клиника: " + ", ".join(b for b in clinic_bits if b), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

    # What a vet asks first, in a box of its own.
    pdf.ln(4)
    pdf.set_fill_color(*BAND)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*ALERT)
    pdf.cell(0, 7, "Здоровье и аллергии", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*INK)

    def box_line(label: str, text: str, bold_label: bool = True) -> None:
        pdf.set_font("DejaVu", "B" if bold_label else "", 10)
        pdf.cell(pdf.get_string_width(label) + 2, 6, label, fill=True)
        pdf.set_font("DejaVu", "", 10)
        pdf.multi_cell(0, 6, text, align="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if profile.get("allergies"):
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(0, 6, "Аллергии", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", "", 10)
        for a in profile["allergies"]:
            line = a["substance"] + (f": {a['reaction']}" if a.get("reaction") else "")
            pdf.multi_cell(0, 6, f"  {line}", align="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    elif profile.get("allergies_none_known"):
        box_line("Аллергии: ", "не выявлено")
    elif pet.get("health_notes"):
        # The notes were once the only place for allergies: «не указаны» above a note that
        # says «аллергия на курицу» would mislead.
        box_line("Аллергии: ", "не заполнены, смотрите заметки ниже")
    else:
        box_line("Аллергии: ", "не указаны")
    if profile.get("conditions"):
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(0, 6, "Хронические состояния", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", "", 10)
        for c in profile["conditions"]:
            line = (
                c["name"]
                + (f" (с {c['since_year']} года)" if c.get("since_year") else "")
                + (f": {c['note']}" if c.get("note") else "")
            )
            pdf.multi_cell(0, 6, f"  {line}", align="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if pet.get("health_notes"):
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(0, 6, "Заметки", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", "", 10)
        pdf.multi_cell(0, 6, pet["health_notes"], align="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def draw_course(pdf: "_Card", c: dict, past: bool) -> None:
    """One medication course: what, how much and when, what for, who prescribed it, how it went."""
    name = c["name"] + (f", {c['strength']}" if c.get("strength") else "")
    pdf.row(name, bold_left=True)
    dose = f"{c['dose_text']}, " if c.get("dose_text") else ""
    pdf.muted(f"{dose}{c['schedule_text']}")
    if c.get("purpose"):
        pdf.muted(f"От чего: {c['purpose']}")
    if c.get("prescribed_by"):
        pdf.muted(f"Назначил: {c['prescribed_by']}")
    if c.get("comment"):
        pdf.muted(c["comment"])
    period = _period(c, past)
    if period:
        pdf.muted(period)
    if c.get("given") or c.get("skipped"):
        skipped = f", пропущено {c['skipped']}" if c.get("skipped") else ""
        pdf.muted(f"Дано доз: {c['given']}{skipped}")
    pdf.ln(1)


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
        standing = {"overdue": " (просрочено)", "soon": " (скоро)"}.get(r["status"], "")
        lines.append(f"Следующая: {_date(r['next_due'])}{standing}")
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


def _due_items(card: dict) -> list[tuple[int, str, str, str, tuple]]:
    """What needs doing, worst first: ``(days, title, kind label, right-hand text, colour)``.

    The repeats that are overdue or near, and certificates kept only as documents that have
    expired or are about to. A record replaced by a newer one has no status and is not here.
    """
    items = []
    for r in card["timeline_records"]:
        if r["status"] not in ("overdue", "soon"):
            continue
        overdue = r["status"] == "overdue"
        items.append(
            (
                r["days_left"] if r["days_left"] is not None else 0,
                r["title"],
                KIND_LABELS.get(r["kind"], r["kind"]) + f", сделано {_date(r['date'])}",
                f"{'Просрочено' if overdue else 'Скоро'}, {_date(r['next_due'])}",
                ALERT if overdue else AMBER,
            )
        )
    for v in card["vaccinations"]:
        if v["status"] not in ("expired", "soon"):
            continue
        items.append(
            (
                v["days_left"] if v["days_left"] is not None else 0,
                v["title"],
                "Сертификат в документах",
                f"{STATUS_LABELS[v['status']]}, до {_date(v['expires_at'])}",
                STATUS_COLORS[v["status"]],
            )
        )
    return sorted(items, key=lambda item: item[0])


def _has_repeats(card: dict) -> bool:
    """Is there anything whose date is watched: a repeating record or a certificate with an end?"""
    return any(r["kind"] in ("vaccination", "parasite") for r in card["timeline_records"]) or any(
        v.get("expires_at") for v in card["vaccinations"]
    )


def _due_section(pdf: _Card, card: dict) -> None:
    items = _due_items(card)
    if not items and not _has_repeats(card):
        return
    pdf.section("Что пора сделать")
    if not items:
        pdf.muted("Просроченного и близкого по сроку нет.")
        return
    for _days, title, what, right, color in items:
        pdf.row(title, right, color, bold_left=True)
        pdf.muted(what)
        pdf.ln(1)


def render_medical_card_pdf(card: dict) -> bytes:
    pet = card["pet"]
    pdf = _Card(pet["name"], card["generated_at"])
    pdf.alias_nb_pages()

    # Page one: now. Readable alone, at an appointment.
    pdf.add_page()
    draw_header(pdf, card, "МЕДИЦИНСКАЯ КАРТА")
    weight = card.get("weight")
    if weight:
        pdf.ln(3)
        pdf.row(f"Вес: {_number(weight['latest']['value'])} кг", _date(weight["latest"]["date"]), MUTED)
    _due_section(pdf, card)
    pdf.section("Лекарства сейчас")
    if card["medications"]:
        for c in card["medications"]:
            draw_course(pdf, c, past=False)
    else:
        pdf.muted("Сейчас не принимает.")

    # The record from the birth on, on the pages after.
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 15)
    pdf.set_text_color(*INK)
    pdf.cell(0, 9, "История", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.section("Хронология")
    rows = _timeline(card)
    if len(rows) > (1 if pet.get("birth_date") else 0):
        _section_table(pdf, rows)
    else:
        pdf.muted("Записей о прививках, обработках, визитах и операциях нет.")

    if card["past_courses"]:
        pdf.section("Прошлые курсы препаратов")
        for c in card["past_courses"]:
            draw_course(pdf, c, past=True)

    _weight_section(pdf, weight)
    _events_section(pdf, card["event_summary"])
    _documents_section(pdf, card["documents"])
    return bytes(pdf.output())
