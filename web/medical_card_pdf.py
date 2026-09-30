"""The medical card as a PDF (A4), for a vet.

Built with fpdf2 and the DejaVu Sans fonts bundled in ``web/fonts``: the
built-in PDF fonts have no Cyrillic. Plain black on white, meant to be read
on paper or on a phone in a messenger, not to look like the app.
"""

import os
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
MARGIN = 16
INK = (31, 27, 22)
MUTED = (95, 88, 80)
LINE = (210, 203, 190)
ALERT = (179, 38, 30)
AMBER = (154, 88, 0)
BAND = (250, 246, 239)

CATEGORY_LABELS = {"lab_result": "Анализ", "conclusion": "Заключение"}
STATUS_LABELS = {"valid": "Действует", "soon": "Скоро истекает", "expired": "Истекла", "none": "Срок не указан"}
STATUS_COLORS = {"valid": INK, "soon": AMBER, "expired": ALERT, "none": MUTED}
TARGET_LABELS = {"fleas_ticks": "от блох и клещей", "worms": "от глистов", "both": "от блох, клещей и глистов"}
# The kinds of record, in the order a vet reads them: the title of the section, and whether it is shown when empty.
RECORD_SECTIONS = [
    ("vaccination", "Прививки", True),
    ("parasite", "Обработки от паразитов", True),
    ("visit", "Визиты и диагнозы", False),
    ("procedure", "Операции и процедуры", False),
]


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


def render_medical_card_pdf(card: dict) -> bytes:
    pet = card["pet"]
    pdf = _Card(pet["name"], card["generated_at"])
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, "МЕДИЦИНСКАЯ КАРТА", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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

    def record_lines(r: dict) -> None:
        title = r["title"] + (f" (серия {r['batch']})" if r.get("batch") else "")
        right, color = "", INK
        if r["status"] == "overdue":
            right, color = f"Просрочено, {_date(r['next_due'])}", ALERT
        elif r["status"] == "soon":
            right, color = f"Скоро, {_date(r['next_due'])}", AMBER
        elif r["status"] == "ok":
            right = f"Следующая {_date(r['next_due'])}"
        pdf.row(title, right, color, bold_left=not r["superseded"])
        bits = [f"Сделано {_date(r['date'])}" if r["kind"] in ("vaccination", "parasite") else _date(r["date"])]
        if r.get("target"):
            bits.append(TARGET_LABELS.get(r["target"], r["target"]))
        if r["kind"] not in ("vaccination", "parasite") and r.get("next_due"):
            bits.append(f"повторно {_date(r['next_due'])}")
        if r.get("clinic"):
            bits.append(r["clinic"])
        if r.get("vet"):
            bits.append(f"врач {r['vet']}")
        pdf.muted(", ".join(bits))
        for label, key in (("Диагноз", "diagnosis"), ("Рекомендации", "recommendations"), ("Заметка", "note")):
            if r.get(key):
                pdf.muted(f"{label}: {r[key]}")
        pdf.ln(1)

    records = card.get("records") or {}
    counts = card.get("record_counts") or {}
    for kind, title, always in RECORD_SECTIONS:
        rows = records.get(kind) or []
        legacy = card["vaccinations"] if kind == "vaccination" else []
        if not rows and not legacy and not always:
            continue
        pdf.section(title)
        for r in rows:
            record_lines(r)
        for v in legacy:  # a certificate kept only as a document
            label = STATUS_LABELS[v["status"]]
            if v["expires_at"]:
                label = f"{label}, до {_date(v['expires_at'])}"
            pdf.row(v["title"], label, STATUS_COLORS[v["status"]])
        if not rows and not legacy:
            pdf.muted("Не добавлено.")
        hidden = counts.get(kind, len(rows)) - len(rows)
        if hidden > 0:
            pdf.muted(f"Ещё {hidden} в приложении.")

    def course_lines(c: dict, past: bool) -> None:
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

    pdf.section("Лекарства сейчас")
    if card["medications"]:
        for c in card["medications"]:
            course_lines(c, past=False)
    else:
        pdf.muted("Сейчас не принимает.")

    if card.get("past_courses"):
        pdf.section("Прошлые курсы")
        for c in card["past_courses"]:
            course_lines(c, past=True)

    pdf.section("Вес")
    weight = card.get("weight")
    if weight:
        pdf.row(f"Последний замер: {_number(weight['latest']['value'])} кг", _date(weight["latest"]["date"]))
        if len(weight["series"]) > 1:
            pdf.ln(1)
            for point in reversed(weight["series"][:-1]):
                pdf.row(f"{_number(point['value'])} кг", _date(point["date"]), MUTED)
    else:
        pdf.muted("Замеров нет.")

    if card["documents"]:
        pdf.section("Последние результаты")
        for d in card["documents"]:
            pdf.row(d["title"], f"{CATEGORY_LABELS.get(d['category'], 'Документ')}, {_date(d['added'])}", MUTED)

    return bytes(pdf.output())
