"""The medical card as a PDF (A4), for a vet.

Page one is «now»: who the animal is, what a vet must know first, what is due,
what it takes. It reads alone, at an appointment. The pages after it are the
record, kept short to read: the timeline year by year, the courses that are
over, the weight as a curve with its range per year, what the diary holds,
the documents. What is only bulk is summed up, not listed (every single
weight, every year of a count): a history a vet cannot skim is not read.

Plain black on white, one typeface (DejaVu Sans, bundled in ``web/fonts``: the
built-in PDF fonts have no Cyrillic), four sizes, one colour for what is wrong
(overdue, allergies) and one for what is soon. Every status is also a word, so
it survives a black-and-white print. Meant to be read on paper or on a phone in
a messenger, not to look like the app.
"""

import os
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
MARGIN = 18

# The four sizes: the animal's name, a section, the text, and what is secondary.
NAME_SIZE, SECTION_SIZE, BODY_SIZE, META_SIZE = 22, 12, 10, 9

INK = (31, 27, 22)
MUTED = (95, 88, 80)
RULE = (214, 207, 194)
ALERT = (179, 38, 30)  # overdue, allergies: what is wrong
AMBER = (154, 88, 0)  # soon
BAND = (247, 243, 235)  # the one tint: the box a vet reads first, and a year in the timeline

STATUS_LABELS = {"valid": "Действует", "soon": "Скоро истекает", "expired": "Истекла", "none": "Срок не указан"}
STATUS_COLORS = {"valid": INK, "soon": AMBER, "expired": ALERT, "none": MUTED}
CHECK_LABELS = {
    "appetite": "аппетит",
    "thirst": "жажда",
    "stool": "стул",
    "urine": "моча",
    "vomiting": "рвота",
    "cough": "кашель",
    "activity": "активность",
}
TARGET_LABELS = {"fleas_ticks": "от блох и клещей", "worms": "от глистов", "both": "от блох, клещей и глистов"}
# One word each: the timeline's second column is narrow and a long label made every row two lines.
KIND_LABELS = {"vaccination": "Прививка", "parasite": "Обработка", "visit": "Визит", "procedure": "Операция"}
DOCUMENT_CATEGORIES = {
    "vaccination": "Прививки",
    "lab_result": "Анализ",
    "conclusion": "Заключение",
    "imaging": "Снимок",
    "insurance": "Страховка",
    "other": "Другое",
}
TIMELINE_COLUMNS = (22, 26, 130)
RECENT_WEIGHTS = 6
RECENT_YEARS = 4


def _date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso


def _number(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _period(course: dict) -> str:
    """«с 12.05.2026 по 26.05.2026», «с 12.05.2026», «начнётся 05.10.2026»."""
    started, ended = _date(course.get("started_on")), _date(course.get("ended_on"))
    if course.get("status") == "planned" and started:
        return f"начнётся {started}"
    if started and ended:
        return f"с {started} по {ended}"
    if started:
        return f"с {started}"
    return f"закончен {ended}" if ended else ""


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

    @property
    def width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", META_SIZE)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"Медицинская карта: {self.pet_name}. Petzy, {_date(self.generated_at)}", align="L")
        self.cell(0, 6, f"{self.page_no()} из {{nb}}", align="R")

    def section(self, title: str):
        """A heading: space above, little below; no rule, the space does the separating."""
        if self.get_y() > self.h - 40:  # a heading is never the last line of a page
            self.add_page()
        self.ln(6)
        self.set_font("DejaVu", "B", SECTION_SIZE)
        self.set_text_color(*INK)
        self.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.5)

    def text(self, text: str, size: int = BODY_SIZE, color=INK, bold: bool = False):
        self.set_font("DejaVu", "B" if bold else "", size)
        self.set_text_color(*color)
        self.multi_cell(0, 5, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def muted(self, text: str):
        self.text(text, META_SIZE, MUTED)

    def row(self, left: str, right: str = "", right_color=INK, bold_left: bool = False):
        """One entry: text on the left, a short value on the right."""
        right_w = self.get_string_width(right) + 2 if right else 0
        self.set_font("DejaVu", "B" if bold_left else "", BODY_SIZE)
        self.set_text_color(*INK)
        start_y = self.get_y()
        # The text may take several lines; what follows starts below the last.
        self.multi_cell(self.width - right_w - 2, 5.5, left, align="L", new_x=XPos.LEFT, new_y=YPos.NEXT)
        end_y = self.get_y()
        if right:
            self.set_xy(self.w - self.r_margin - right_w, start_y)
            self.set_font("DejaVu", "", BODY_SIZE)
            self.set_text_color(*right_color)
            self.cell(right_w, 5.5, right, align="R")
        self.set_xy(self.l_margin, max(end_y, start_y + 5.5))


def _clinics(profile: dict) -> list[dict]:
    """The clinics of the profile, the main one first; the single clinic of an older profile is one of them."""
    clinics = profile.get("clinics") or []
    if clinics:
        return clinics
    legacy = profile.get("clinic") or {}
    if legacy.get("name") or legacy.get("vet") or legacy.get("phone"):
        doctors = [{"name": legacy["vet"]}] if legacy.get("vet") else []
        return [{"name": legacy.get("name"), "phone": legacy.get("phone"), "doctors": doctors}]
    return []


def _lower_first(text: str) -> str:
    """«Терапевт» -> «терапевт», as the screen shows it; an abbreviation («УЗИ-врач») stays."""
    return text[:1].lower() + text[1:] if text[1:2] != text[1:2].upper() or not text[1:2].isalpha() else text


def _clinic_line(clinic: dict) -> str:
    """«Вет-клиника Друг, +7 701 000 00 00. Врачи: Иванова, терапевт; Петров, кардиолог.»"""
    head = ", ".join(x for x in (clinic.get("name") or "Клиника", clinic.get("phone")) if x)
    doctors = "; ".join(
        d["name"] + (f", {_lower_first(d['specialty'])}" if d.get("specialty") else "")
        for d in clinic.get("doctors") or []
    )
    if not doctors:
        return head
    return f"{head}. {'Врач' if len(clinic['doctors']) == 1 else 'Врачи'}: {doctors}"


def draw_header(pdf: _Card, card: dict) -> None:
    """The top of page one: the name, who the animal is, and the box a vet reads first."""
    pet = card["pet"]
    profile = card.get("profile") or {}

    pdf.set_font("DejaVu", "B", NAME_SIZE)
    pdf.set_text_color(*INK)
    pdf.cell(0, 11, pet["name"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    facts = [pet.get("species"), pet.get("breed")]
    if pet.get("birth_date"):
        facts.append(f"родился {_date(pet['birth_date'])}" + (f" ({pet['age_text']})" if pet.get("age_text") else ""))
    if pet.get("gender"):
        facts.append(pet["gender"].lower())
    if pet.get("neutered_text"):
        facts.append(pet["neutered_text"])
    pdf.text(", ".join(f for f in facts if f) or "Данные о питомце не заполнены", color=MUTED)

    ids = []
    if profile.get("blood_type"):
        ids.append(f"группа крови {profile['blood_type']}")
    if profile.get("chip_number"):
        ids.append(f"чип {profile['chip_number']}")
    if ids:
        line = ", ".join(ids)
        pdf.text(line[0].upper() + line[1:], color=MUTED)
    for clinic in _clinics(profile):
        pdf.text(_clinic_line(clinic), color=MUTED)
    for label, key in (("Питание", "diet"), ("Условия жизни", "living"), ("Репродуктивный статус", "reproduction")):
        if profile.get(key):
            pdf.text(f"{label}: {profile[key]}", color=MUTED)

    # What a vet asks first: allergies and conditions, in a box of their own.
    pdf.ln(4)
    pdf.set_fill_color(*BAND)
    pdf.set_text_color(*ALERT)
    pdf.set_font("DejaVu", "B", BODY_SIZE)
    pdf.cell(0, 6.5, "  Аллергии и хронические состояния", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*INK)

    def line_in_box(label: str, text: str) -> None:
        pdf.set_font("DejaVu", "B", BODY_SIZE)
        pdf.cell(pdf.get_string_width("  " + label) + 2, 5.5, "  " + label, fill=True)
        pdf.set_font("DejaVu", "", BODY_SIZE)
        pdf.multi_cell(0, 5.5, text, align="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if profile.get("allergies"):
        for a in profile["allergies"]:
            line_in_box("Аллергия", a["substance"] + (f": {a['reaction']}" if a.get("reaction") else ""))
    elif profile.get("allergies_none_known"):
        line_in_box("Аллергии", "не выявлено")
    elif pet.get("health_notes"):
        # The notes were once the only place for allergies: «не указаны» above a note that
        # says «аллергия на курицу» would mislead.
        line_in_box("Аллергии", "не заполнены, смотрите заметки ниже")
    else:
        line_in_box("Аллергии", "не указаны")
    for c in profile.get("conditions") or []:
        since = f" (с {c['since_year']} года)" if c.get("since_year") else ""
        line_in_box("Хроника", c["name"] + since + (f": {c['note']}" if c.get("note") else ""))
    if pet.get("health_notes"):
        line_in_box("Заметки", pet["health_notes"])


def draw_course(pdf: _Card, c: dict) -> None:
    """One medication course in two lines: the name with its dates, then everything else it needs said."""
    if pdf.get_y() > pdf.h - 32:  # the name never stays on one page and its line on the next
        pdf.add_page()
    name = c["name"] + (f", {c['strength']}" if c.get("strength") else "")
    pdf.row(name, _period(c), MUTED, bold_left=True)
    bits = [", ".join(x for x in (c.get("dose_text"), c.get("schedule_text")) if x)]
    if c.get("purpose"):
        bits.append(f"от чего: {c['purpose']}")
    if c.get("prescribed_by"):
        bits.append(f"назначил {c['prescribed_by']}")
    if c.get("given") or c.get("skipped"):
        skipped = f", пропущено {c['skipped']}" if c.get("skipped") else ""
        bits.append(f"дано {c['given']}{skipped}")
    if c.get("comment"):
        bits.append(c["comment"])
    pdf.muted(". ".join(b[0].upper() + b[1:] for b in bits if b) + ".")
    pdf.ln(1.5)


def _record_details(r: dict, home: dict) -> str:
    """The lines under a record's title in the timeline. The clinic and the vet are left out when they are
    the ones in the header: said on every row, they are noise."""
    lines = [r["title"] + (f" (серия {r['batch']})" if r.get("batch") else "")]
    if r.get("target"):
        lines.append(TARGET_LABELS.get(r["target"], r["target"]).capitalize())
    if r["kind"] in ("vaccination", "parasite") and r.get("next_due") and not r["superseded"]:
        standing = {"overdue": " (просрочено)", "soon": " (скоро)"}.get(r["status"], "")
        lines.append(f"Следующая: {_date(r['next_due'])}{standing}")
    elif r.get("next_due") and r["kind"] not in ("vaccination", "parasite"):
        lines.append(f"Повторно: {_date(r['next_due'])}")
    clinic = r.get("clinic") if r.get("clinic") != home.get("name") else None
    vet = r.get("vet") if r.get("vet") != home.get("vet") else None
    where = ", ".join(x for x in (clinic, f"врач {vet}" if vet else None) if x)
    if where:
        lines.append(where)
    for label, key in (
        ("Жалоба", "complaint"),
        ("Диагноз", "diagnosis"),
        ("Рекомендации", "recommendations"),
        ("Заметка", "note"),
    ):
        if r.get(key):
            lines.append(f"{label}: {r[key]}")
    if r.get("documents"):
        lines.append("Документы: " + ", ".join(d["title"] for d in r["documents"]))
    return "\n".join(lines)


def _timeline(card: dict) -> list[dict]:
    """Everything dated, oldest first: the birth, the records, the certificates kept only as documents."""
    # With one clinic the header already names it and its doctor: said on every row it is noise. With several, each
    # record says which one it was.
    clinics = _clinics(card.get("profile") or {})
    home = (
        {"name": clinics[0].get("name"), "vet": (clinics[0].get("doctors") or [{}])[0].get("name")}
        if len(clinics) == 1
        else {}
    )
    rows = []
    if card["pet"].get("birth_date"):
        rows.append({"date": card["pet"]["birth_date"], "what": "Рождение", "details": ""})
    for r in card["timeline_records"]:
        rows.append(
            {"date": r["date"], "what": KIND_LABELS.get(r["kind"], r["kind"]), "details": _record_details(r, home)}
        )
    added = {d["id"]: d["added"] for d in card["documents"]}
    for v in card["vaccinations"]:
        if not added.get(v["id"]):
            continue
        until = f"\nДействует до {_date(v['expires_at'])}" if v.get("expires_at") else ""
        rows.append({"date": added[v["id"]], "what": "Прививка", "details": f"{v['title']} (сертификат){until}"})
    rows.sort(key=lambda row: row["date"])
    return rows


def _timeline_table(pdf: _Card, rows: list[dict]) -> None:
    pdf.set_font("DejaVu", "", META_SIZE)
    pdf.set_text_color(*INK)
    pdf.set_fill_color(255, 255, 255)  # a table fills its cells with the current colour: only the years are tinted
    pdf.set_draw_color(*RULE)
    year_style = FontFace(emphasis="BOLD", color=INK, fill_color=BAND)
    with pdf.table(
        col_widths=TIMELINE_COLUMNS,
        text_align=("LEFT", "LEFT", "LEFT"),
        v_align="T",
        line_height=4.8,
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
    """The weight over time: a line on a frame, the range at the left, the first and last date below."""
    height = 34
    if pdf.get_y() + height + 12 > pdf.h - 20:
        pdf.add_page()
    left, width = pdf.l_margin + 12, pdf.width - 12
    top = pdf.get_y() + 1
    values = [p["value"] for p in series]
    low, high = min(values), max(values)
    span = (high - low) or 1
    days = [datetime.strptime(p["date"], "%Y-%m-%d").toordinal() for p in series]
    total = (days[-1] - days[0]) or 1

    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.2)
    pdf.rect(left, top, width, height)
    pdf.set_font("DejaVu", "", META_SIZE)
    pdf.set_text_color(*MUTED)
    pdf.set_xy(pdf.l_margin, top - 1)
    pdf.cell(11, 4, _number(high), align="R")
    pdf.set_xy(pdf.l_margin, top + height - 3)
    pdf.cell(11, 4, _number(low), align="R")

    points = [
        (left + 2 + (d - days[0]) / total * (width - 4), top + height - 3 - (v - low) / span * (height - 6))
        for d, v in zip(days, values)
    ]
    pdf.set_draw_color(*INK)
    pdf.set_line_width(0.5)
    if len(points) > 1:
        pdf.polyline(points)
    pdf.set_fill_color(*INK)
    x, y = points[-1]
    pdf.ellipse(x - 1, y - 1, 2, 2, style="F")
    pdf.set_line_width(0.2)

    pdf.set_font("DejaVu", "", META_SIZE)
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
    pdf.row(f"Последний замер: {_number(last['value'])} кг", _date(last["date"]), MUTED, bold_left=True)
    if len(series) == 1:
        return
    change = last["value"] - first["value"]
    sign = "+" if change > 0 else ""
    pdf.muted(
        f"Первый: {_number(first['value'])} кг ({_date(first['date'])}). "
        f"За всё время {sign}{_number(round(change, 2))} кг. Замеров: {len(series)}."
    )
    _weight_chart(pdf, series)
    # Not every measurement: the range of each year says what a vet asks, and the latest few say where it is now.
    by_year: dict[str, list[float]] = {}
    for p in series:
        by_year.setdefault(p["date"][:4], []).append(p["value"])
    pdf.muted("По годам: " + "; ".join(f"{y} {_number(min(v))}–{_number(max(v))} кг" for y, v in by_year.items()) + ".")
    pdf.muted(
        "Последние: " + ", ".join(f"{_number(p['value'])} ({_date(p['date'])})" for p in series[-RECENT_WEIGHTS:]) + "."
    )


def _events_section(pdf: _Card, summary: list[dict]) -> None:
    pdf.section("Записи из дневника")
    if not summary:
        pdf.muted("Записей нет.")
        return
    for row in summary:
        if pdf.get_y() > pdf.h - 34:  # a title and its line of numbers stay on one page
            pdf.add_page()
        pdf.row(row["label"], f"всего {row['total']}", bold_left=True)
        years = list(row["years"].items())
        recent, older = years[-RECENT_YEARS:], years[:-RECENT_YEARS]
        by_year = ", ".join(f"{y}: {n}" for y, n in recent)
        earlier = f"раньше {sum(n for _, n in older)}, " if older else ""
        pdf.muted(f"С {_date(row['first'])} по {_date(row['last'])}. По годам: {earlier}{by_year}.")
        pdf.ln(1)


def _documents_section(pdf: _Card, documents: list[dict]) -> None:
    pdf.section("Документы")
    if not documents:
        pdf.muted("Документов нет.")
        return
    for d in documents:
        kind = DOCUMENT_CATEGORIES.get(d["category"], "Документ")
        until = f", до {_date(d['expires_at'])}" if d.get("expires_at") else ""
        pdf.row(d["title"], f"{kind}{until}, {_date(d['added'])}", MUTED)


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
        pdf.ln(1.5)


STANDING_LIMIT = 8


def _standing_items(card: dict) -> list[dict]:
    """The vaccinations and treatments in force, newest first: what a vet looks for on page one (is the rabies
    shot current, and until when). The overdue and near ones are in «Что пора сделать» already, said once."""
    return sorted(
        (
            r
            for r in card["timeline_records"]
            if r["kind"] in ("vaccination", "parasite") and not r["superseded"] and r["status"] in ("ok", "none")
        ),
        key=lambda r: r["date"],
        reverse=True,
    )


def _standing_section(pdf: _Card, card: dict) -> None:
    items = _standing_items(card)
    if not items:
        return
    pdf.section("Прививки и обработки в силе")
    for r in items[:STANDING_LIMIT]:
        pdf.row(
            r["title"],
            f"Следующая {_date(r['next_due'])}" if r.get("next_due") else "Повтор не назначен",
            bold_left=True,
        )
        pdf.muted(f"{KIND_LABELS.get(r['kind'], r['kind'])}, сделано {_date(r['date'])}")
        pdf.ln(1.5)
    if len(items) > STANDING_LIMIT:
        pdf.muted(f"Ещё {len(items) - STANDING_LIMIT} в хронологии.")


def _visit_prep_section(pdf: _Card, prep: dict | None) -> None:
    """What the household wants to tell the vet at this appointment: the first thing a vet asks about."""
    if not prep:
        return
    pdf.section("На приём")
    if prep.get("complaint"):
        pdf.text(prep["complaint"])
    checks = prep.get("checks") or {}
    changed = [CHECK_LABELS[k] for k in CHECK_LABELS if checks.get(k) == "changed"]
    normal = [CHECK_LABELS[k] for k in CHECK_LABELS if checks.get(k) == "normal"]
    if changed:
        pdf.text("Изменилось: " + ", ".join(changed) + ".", color=ALERT)
    if normal:
        pdf.muted("Как обычно: " + ", ".join(normal) + ".")


def render_medical_card_pdf(card: dict) -> bytes:
    pet = card["pet"]
    pdf = _Card(pet["name"], card["generated_at"])
    pdf.alias_nb_pages()

    # Page one: now. Readable alone, at an appointment.
    pdf.add_page()
    draw_header(pdf, card)
    _visit_prep_section(pdf, card.get("visit_prep"))
    weight = card.get("weight")
    if weight:
        pdf.ln(4)
        pdf.row(f"Вес: {_number(weight['latest']['value'])} кг", _date(weight["latest"]["date"]), MUTED)
    _due_section(pdf, card)
    _standing_section(pdf, card)
    pdf.section("Лекарства сейчас")
    if card["medications"]:
        for c in card["medications"]:
            draw_course(pdf, c)
    else:
        pdf.muted("Сейчас не принимает.")

    # The record from the birth on, on the pages after.
    pdf.add_page()
    pdf.section("Хронология")
    rows = _timeline(card)
    if len(rows) > (1 if pet.get("birth_date") else 0):
        _timeline_table(pdf, rows)
    else:
        pdf.muted("Записей о прививках, обработках, визитах и операциях нет.")

    if card["past_courses"]:
        pdf.section("Прошлые курсы препаратов")
        for c in card["past_courses"]:
            draw_course(pdf, c)

    _weight_section(pdf, weight)
    _events_section(pdf, card["event_summary"])
    _documents_section(pdf, card["documents"])
    return bytes(pdf.output())
