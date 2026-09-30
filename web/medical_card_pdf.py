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

    if pet.get("health_notes"):
        pdf.ln(4)
        pdf.set_fill_color(*BAND)
        pdf.set_draw_color(*ALERT)
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_text_color(*ALERT)
        pdf.cell(0, 7, "Здоровье и аллергии", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 6, pet["health_notes"], align="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.section("Прививки")
    if card["vaccinations"]:
        for v in card["vaccinations"]:
            label = STATUS_LABELS[v["status"]]
            if v["expires_at"]:
                label = f"{label}, до {_date(v['expires_at'])}"
            pdf.row(v["title"], label, STATUS_COLORS[v["status"]])
    else:
        pdf.muted("Не добавлено.")

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
