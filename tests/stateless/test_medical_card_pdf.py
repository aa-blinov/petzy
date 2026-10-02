"""The medical card as a PDF: page one is «now», the pages after are the whole history."""

import io
from datetime import datetime, timedelta
from urllib.parse import unquote

import pytest
from pypdf import PdfReader

from web.security import create_access_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _pdf(client, token, pet, query=""):
    response = client.get(f"/api/pets/{pet['_id']}/medical-card/pdf{query}", headers=_auth(token))
    assert response.status_code == 200, response.get_data(as_text=True)[:200]
    return response, "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages)


def _first_page(client, token, pet) -> str:
    response = client.get(f"/api/pets/{pet['_id']}/medical-card/pdf", headers=_auth(token))
    return PdfReader(io.BytesIO(response.data)).pages[0].extract_text()


def _flat(text: str) -> str:
    """The text on one line: a table cell wraps «Обработка от паразитов» over two."""
    return " ".join(text.split())


def _record(mock_db, pet, kind="vaccination", title="Рабизин", day="2024-05-01", **extra):
    mock_db["medical_records"].insert_one(
        {
            "pet_id": str(pet["_id"]),
            "kind": kind,
            "title": title,
            "date": day,
            "next_due": None,
            "document_ids": [],
            "created_at": datetime(2024, 1, 1),
            **extra,
        }
    )


@pytest.mark.health
class TestTheWholeRecord:
    def test_nothing_is_cut_at_ten(self, client, mock_db, regular_user_token, test_pet):
        for i in range(25):
            _record(mock_db, test_pet, title=f"Вакцина номер {i:02d}", day=f"20{i % 20 + 5:02d}-03-10")
        _, text = _pdf(client, regular_user_token, test_pet)
        assert all(f"Вакцина номер {i:02d}" in text for i in range(25))
        assert "в приложении" not in text  # nothing is cut, so nothing is «ещё N»

    def test_it_reads_oldest_first_by_year(self, client, mock_db, regular_user_token, test_pet):
        _record(mock_db, test_pet, title="Поздняя", day="2025-06-01")
        _record(mock_db, test_pet, title="Ранняя", day="2021-06-01")
        _record(mock_db, test_pet, kind="visit", title="Средняя", day="2023-06-01")
        _, text = _pdf(client, regular_user_token, test_pet)
        text = text[text.index("Хронология") :]
        assert text.index("Ранняя") < text.index("Средняя") < text.index("Поздняя")
        assert text.index("2021") < text.index("2023") < text.index("2025")

    def test_the_birth_opens_the_history(self, client, mock_db, regular_user_token, test_pet):
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"birth_date": "2019-01-15"}})
        _record(mock_db, test_pet, day="2019-03-10")
        _, text = _pdf(client, regular_user_token, test_pet)
        assert "15.01.2019" in text and "Рождение" in text
        text = text[text.index("Хронология") :]
        assert text.index("Рождение") < text.index("Рабизин")

    def test_every_detail_of_a_record_is_there(self, client, mock_db, regular_user_token, test_pet):
        _record(
            mock_db,
            test_pet,
            kind="visit",
            title="Осмотр",
            day="2024-08-14",
            diagnosis="Гастрит",
            recommendations="Диета",
            clinic="Друг",
            vet="Иванова",
            note="Вес стабилен",
        )
        _record(
            mock_db, test_pet, kind="parasite", title="Дронтал", day="2024-09-01", target="worms", next_due="2099-01-01"
        )
        _, text = _pdf(client, regular_user_token, test_pet)
        text = _flat(text)
        for needle in (
            "Визит",
            "Диагноз: Гастрит",
            "Рекомендации: Диета",
            "врач Иванова",
            "Заметка: Вес стабилен",
            "Обработка",
            "От глистов",
            "01.01.2099",
        ):
            assert needle in text, needle

    def test_a_certificate_kept_as_a_document_is_in_the_timeline(self, client, mock_db, regular_user_token, test_pet):
        mock_db["documents"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "category": "vaccination",
                "title": "Сертификат Эурикан",
                "expires_at": "2099-02-02",
                "created_at": datetime(2022, 4, 5, 12, 0),
                "file_id": "f",
            }
        )
        _, text = _pdf(client, regular_user_token, test_pet)
        text = _flat(text)
        assert "Сертификат Эурикан (сертификат)" in text and "05.04.2022" in text and "Действует до 02.02.2099" in text


@pytest.mark.health
class TestCoursesWeightEventsDocuments:
    def test_every_past_course_is_listed(self, client, mock_db, regular_user_token, test_pet):
        for i in range(15):
            mock_db["medications"].insert_one(
                {
                    "pet_id": str(test_pet["_id"]),
                    "name": f"Курс-{i:02d}",
                    "is_active": False,
                    "started_on": "2023-01-01",
                    "ended_on": f"2023-02-{i + 1:02d}",
                    "schedule": {"days": [0], "times": ["10:00"]},
                }
            )
        _, text = _pdf(client, regular_user_token, test_pet)
        assert all(f"Курс-{i:02d}" in text for i in range(15))

    def test_the_card_says_how_many_past_courses_there_are(self, client, mock_db, regular_user_token, test_pet):
        for i in range(12):
            mock_db["medications"].insert_one(
                {
                    "pet_id": str(test_pet["_id"]),
                    "name": f"К{i}",
                    "is_active": False,
                    "schedule": {"days": [0], "times": ["10:00"]},
                }
            )
        card = client.get(f"/api/pets/{test_pet['_id']}/medical-card", headers=_auth(regular_user_token)).get_json()[
            "card"
        ]
        assert len(card["past_courses"]) == 10 and card["past_courses_total"] == 12

    def test_all_weights_are_there_with_the_change(self, client, mock_db, regular_user_token, test_pet):
        for i in range(40):
            mock_db["events"].insert_one(
                {
                    "pet_id": str(test_pet["_id"]),
                    "type": "weight",
                    "date_time": datetime(2022 + i // 12, i % 12 + 1, 1, 9, 0),
                    "fields": {"weight": 4.0 + i * 0.1},
                }
            )
        _, text = _pdf(client, regular_user_token, test_pet)
        text = _flat(text)
        assert "Замеров: 40" in text and "Первый: 4 кг (01.01.2022)" in text and "За всё время +3,9 кг" in text
        # not every measurement: the range of each year, and the latest few
        assert "По годам: 2022 4–5,1 кг; 2023 5,2–6,3 кг" in text
        assert "Последние: " in text and "7,9 (01.04.2025)" in text
        assert "5,7 (01.06.2023)" not in text  # one from the middle is summed up in its year, not listed

    def test_the_diary_is_summarised_per_kind_and_year(self, client, mock_db, regular_user_token, test_pet):
        pid = str(test_pet["_id"])
        for when in (datetime(2024, 2, 1, 8), datetime(2024, 9, 1, 8), datetime(2025, 3, 1, 8)):
            mock_db["events"].insert_one({"pet_id": pid, "type": "asthma", "date_time": when, "fields": {}})
        mock_db["events"].insert_one(
            {"pet_id": pid, "type": "weight", "date_time": datetime(2025, 3, 1, 8), "fields": {"weight": 4.0}}
        )
        _, text = _pdf(client, regular_user_token, test_pet)
        assert "Приступ астмы" in text and "всего 3" in text
        assert "С 01.02.2024 по 01.03.2025. По годам: 2024: 2, 2025: 1" in text
        # the weight has its own section, not a line among the kinds of event
        assert "Вес\n" in text and "Вес всего" not in text

    def test_all_documents_are_listed(self, client, mock_db, regular_user_token, test_pet):
        for title, category in [("Анализ крови", "lab_result"), ("Полис", "insurance"), ("МРТ", "imaging")]:
            mock_db["documents"].insert_one(
                {
                    "pet_id": str(test_pet["_id"]),
                    "category": category,
                    "title": title,
                    "created_at": datetime(2025, 1, 2),
                    "file_id": "f",
                }
            )
        _, text = _pdf(client, regular_user_token, test_pet)
        for needle in ("Анализ крови", "Полис", "МРТ", "Страховка", "Снимок", "Анализ, 02.01.2025"):
            assert needle in text, needle

    def test_an_empty_pet_gets_an_honest_empty_history(self, client, mock_db, regular_user_token, test_pet):
        _, text = _pdf(client, regular_user_token, test_pet)
        for needle in (
            "Медицинская карта: ",
            "Сейчас не принимает.",
            "Замеров нет.",
            "Записей нет.",
            "Документов нет.",
        ):
            assert needle in text, needle


@pytest.mark.health
class TestTheEndpoint:
    def test_the_file_is_named_and_not_cached(self, client, regular_user_token, test_pet):
        response, _ = _pdf(client, regular_user_token, test_pet, "?tz=Asia/Almaty")
        assert response.content_type == "application/pdf" and response.headers["Cache-Control"] == "private, no-store"
        assert unquote(response.headers["Content-Disposition"].split("''")[1]).startswith("медкарта_")

    def test_a_shared_user_may_download_it_a_stranger_may_not(self, client, mock_db, test_pet):
        mock_db["users"].insert_one({"username": "friend", "is_active": True, "password_hash": "x"})
        mock_db["users"].insert_one({"username": "stranger", "is_active": True, "password_hash": "x"})
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["friend"]}})
        assert _pdf(client, create_access_token("friend"), test_pet)[0].status_code == 200
        stranger = client.get(
            f"/api/pets/{test_pet['_id']}/medical-card/pdf", headers=_auth(create_access_token("stranger"))
        )
        assert stranger.status_code in (403, 404)

    def test_no_login_no_history(self, client, test_pet):
        assert client.get(f"/api/pets/{test_pet['_id']}/medical-card/pdf").status_code == 401

    def test_a_long_history_runs_onto_more_pages(self, client, mock_db, regular_user_token, test_pet):
        for i in range(120):
            _record(mock_db, test_pet, title=f"Запись {i:03d}", day=f"20{i % 25 + 1:02d}-01-01")
        response, _ = _pdf(client, regular_user_token, test_pet)
        assert len(PdfReader(io.BytesIO(response.data)).pages) >= 3


@pytest.mark.health
class TestPageOne:
    """The first page is what an appointment needs, readable without the rest."""

    def test_it_has_what_to_do_now_and_the_medicines_but_not_the_history(
        self, client, mock_db, regular_user_token, test_pet
    ):
        _record(mock_db, test_pet, title="Рабизин", day="2025-05-01", next_due="2020-01-01")
        _record(
            mock_db,
            test_pet,
            kind="parasite",
            title="Дронтал",
            day="2026-09-20",
            target="worms",
            next_due=(datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
        )
        mock_db["medications"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "name": "Габапентин",
                "is_active": True,
                "default_dose": 1,
                "dose_unit": "таб",
                "schedule": {"days": list(range(7)), "times": ["08:00"]},
            }
        )
        mock_db["events"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date_time": datetime(2026, 9, 28, 9, 0),
                "fields": {"weight": 4.5},
            }
        )
        page = _flat(_first_page(client, regular_user_token, test_pet))
        for needle in (
            "Что пора сделать",
            "Рабизин",
            "Просрочено",
            "Дронтал",
            "Скоро",
            "Лекарства сейчас",
            "Габапентин",
            "Вес: 4,5 кг",
        ):
            assert needle in page, needle
        assert "Хронология" not in page and "История" not in page

    def test_the_history_starts_on_the_second_page(self, client, mock_db, regular_user_token, test_pet):
        _record(mock_db, test_pet, title="Рабизин", day="2024-05-01")
        response, text = _pdf(client, regular_user_token, test_pet)
        pages = PdfReader(io.BytesIO(response.data)).pages
        assert (
            len(pages) >= 2 and "Хронология" in pages[1].extract_text() and "Хронология" not in pages[0].extract_text()
        )

    def test_nothing_overdue_says_so_when_dates_are_watched(self, client, mock_db, regular_user_token, test_pet):
        _record(
            mock_db,
            test_pet,
            title="Рабизин",
            day="2026-09-20",
            next_due=(datetime.now() + timedelta(days=300)).strftime("%Y-%m-%d"),
        )
        page = _flat(_first_page(client, regular_user_token, test_pet))
        assert "Что пора сделать" in page and "Просроченного и близкого по сроку нет." in page

    def test_no_dates_watched_no_section(self, client, mock_db, regular_user_token, test_pet):
        _record(mock_db, test_pet, kind="visit", title="Осмотр", day="2024-05-01")
        assert "Что пора сделать" not in _first_page(client, regular_user_token, test_pet)

    def test_a_replaced_record_is_not_called_overdue(self, client, mock_db, regular_user_token, test_pet):
        _record(mock_db, test_pet, title="Рабизин", day="2024-01-10", next_due="2025-01-10", created=0)
        _record(
            mock_db,
            test_pet,
            title="Рабизин",
            day="2025-09-20",
            next_due=(datetime.now() + timedelta(days=300)).strftime("%Y-%m-%d"),
            created=5,
        )
        page = _flat(_first_page(client, regular_user_token, test_pet))
        assert "Просрочено" not in page

    def test_an_expired_certificate_kept_as_a_document_is_called_out(
        self, client, mock_db, regular_user_token, test_pet
    ):
        mock_db["documents"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "category": "vaccination",
                "title": "Сертификат Эурикан",
                "expires_at": "2020-02-02",
                "created_at": datetime(2019, 4, 5),
                "file_id": "f",
            }
        )
        page = _flat(_first_page(client, regular_user_token, test_pet))
        assert "Сертификат Эурикан" in page and "Истекла, до 02.02.2020" in page

    def test_the_timeline_marks_a_repeat_that_is_overdue(self, client, mock_db, regular_user_token, test_pet):
        _record(mock_db, test_pet, title="Рабизин", day="2025-05-01", next_due="2026-01-01")
        _, text = _pdf(client, regular_user_token, test_pet)
        assert "Следующая: 01.01.2026 (просрочено)" in _flat(text)

    def test_a_long_medicine_name_does_not_run_into_the_line_under_it(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """A name that wraps onto two lines pushes what follows down; it used to be drawn over it."""
        mock_db["medications"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "name": "Очень длинное название лекарства " * 4,
                "is_active": True,
                "schedule": {"days": [0], "times": ["10:00"]},
            }
        )
        lines = []  # (y, text): a PDF's y grows upward

        def visitor(text, cm, tm, font_dict, font_size):
            if text.strip():
                lines.append((tm[5] if cm == [1, 0, 0, 1, 0, 0] else cm[5], text.strip()))

        response, _ = _pdf(client, regular_user_token, test_pet)
        PdfReader(io.BytesIO(response.data)).pages[0].extract_text(visitor_text=visitor)
        wrapped = [y for y, text in lines if "Очень длинное название" in text]
        schedule = [y for y, text in lines if text.startswith("По пн в 10:00")]
        assert len(wrapped) >= 2 and schedule  # the name really took several lines
        assert schedule[0] < min(wrapped) - 3  # and the schedule is under all of them


class TestWhatIsInForceOnPageOne:
    def test_a_current_vaccination_is_on_the_first_page_with_its_date_and_its_next(
        self, client, mock_db, regular_user_token, test_pet
    ):
        _record(mock_db, test_pet, title="Бешенство", day="2026-05-01", next_due="2027-05-01")
        _, text = _pdf(client, regular_user_token, test_pet)
        first_page = text[: text.index("Хронология")]
        assert "Прививки и обработки в силе" in first_page
        assert "Бешенство" in first_page and "сделано 01.05.2026" in first_page and "Следующая 01.05.2027" in first_page

    def test_an_overdue_one_is_said_once_in_what_is_due_not_again_in_force(
        self, client, mock_db, regular_user_token, test_pet
    ):
        _record(mock_db, test_pet, title="Просроченная", day="2024-01-01", next_due="2025-01-01")
        _, text = _pdf(client, regular_user_token, test_pet)
        first_page = text[: text.index("Хронология")]
        assert first_page.count("Просроченная") == 1

    def test_a_replaced_record_is_not_in_force(self, client, mock_db, regular_user_token, test_pet):
        _record(mock_db, test_pet, title="Бешенство", day="2025-05-01", next_due="2026-11-01")
        _record(mock_db, test_pet, title="Бешенство", day="2026-05-01", next_due="2027-05-01")
        _, text = _pdf(client, regular_user_token, test_pet)
        first_page = text[: text.index("Хронология")]
        assert first_page.count("Бешенство") == 1 and "Следующая 01.05.2027" in first_page

    def test_a_specialty_reads_in_lower_case_as_on_the_screen(self):
        from web.medical_card_pdf import _clinic_line

        line = _clinic_line({"name": "Друг", "doctors": [{"name": "Иванова А. П.", "specialty": "Терапевт"}]})
        assert line.endswith("Иванова А. П., терапевт")
        assert "УЗИ-врач" in _clinic_line({"name": "Друг", "doctors": [{"name": "П", "specialty": "УЗИ-врач"}]})


class TestWhatDoesNotFit:
    def test_a_picture_the_font_cannot_draw_is_said_not_dropped(self, client, mock_db, regular_user_token, test_pet):
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"health_notes": "аллергия на 🍗 курицу"}})
        _, text = _pdf(client, regular_user_token, test_pet)
        assert "аллергия на [значок] курицу" in _flat(text)

    def test_many_medicines_keep_page_one_a_page(self, client, mock_db, regular_user_token, test_pet):
        mock_db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {
                "$set": {
                    "medical_profile": {
                        "allergies": [{"substance": f"Аллерген{i}", "reaction": "зуд"} for i in range(10)],
                        "allergies_none_known": False,
                        "conditions": [{"name": f"Состояние{i}"} for i in range(3)],
                    }
                }
            },
        )
        for i in range(20):
            mock_db["medications"].insert_one(
                {
                    "pet_id": str(test_pet["_id"]),
                    "name": f"Препарат{i:02d}",
                    "type": "Таблетка",
                    "dose_unit": "таб",
                    "default_dose": 1,
                    "is_active": True,
                    "schedule": {"days": list(range(7)), "times": ["08:00", "20:00"]},
                    "created_at": datetime(2026, 1, 1),
                }
            )
        first = _flat(_first_page(client, regular_user_token, test_pet))
        assert all(f"Препарат{i:02d}" in first for i in range(20))
        assert "Аллерген9" in first
        assert "Хронология" not in first
