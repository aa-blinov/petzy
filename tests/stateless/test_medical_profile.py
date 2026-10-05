"""The medical profile: what a vet asks first, kept on the pet and edited by
anyone who has access to it."""

import io

import pytest
from pypdf import PdfReader

from web.security import create_access_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _put(client, token, pet, body):
    return client.put(f"/api/pets/{pet['_id']}/medical-profile", json=body, headers=_auth(token))


def _card(client, token, pet):
    return client.get(f"/api/pets/{pet['_id']}/medical-card", headers=_auth(token)).get_json()["card"]


FULL = {
    "chip_number": "643093100123456",
    "blood_type": "A",
    "allergies": [{"substance": "Курица", "reaction": "зуд, покраснение ушей"}, {"substance": "Амоксициллин"}],
    "conditions": [{"name": "Хронический гастрит", "since_year": 2024, "note": "обострения осенью"}],
    "clinic": {"name": "Вет-клиника Друг", "vet": "Иванова А. П.", "phone": "+7 701 000 00 00"},
}


@pytest.mark.health
class TestSavingTheProfile:
    def test_it_is_saved_and_comes_back_on_the_card(self, client, mock_db, regular_user_token, test_pet):
        response = _put(client, regular_user_token, test_pet, FULL)
        assert response.status_code == 200
        profile = _card(client, regular_user_token, test_pet)["profile"]
        assert profile["chip_number"] == "643093100123456"
        assert [a["substance"] for a in profile["allergies"]] == ["Курица", "Амоксициллин"]
        assert profile["allergies"][1]["reaction"] is None
        assert profile["conditions"][0] == {
            "name": "Хронический гастрит",
            "since_year": 2024,
            "note": "обострения осенью",
        }
        assert profile["clinic"]["vet"] == "Иванова А. П."
        assert profile["updated_at"]

    def test_a_card_with_no_profile_has_an_empty_one(self, client, mock_db, regular_user_token, test_pet):
        profile = _card(client, regular_user_token, test_pet)["profile"]
        assert profile["allergies"] == profile["conditions"] == []
        assert profile["allergies_none_known"] is False
        assert profile["chip_number"] is None and profile["clinic"]["name"] is None

    def test_it_replaces_the_whole_profile(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, FULL)
        _put(client, regular_user_token, test_pet, {"blood_type": "B"})
        profile = _card(client, regular_user_token, test_pet)["profile"]
        assert profile["blood_type"] == "B"
        assert profile["chip_number"] is None and profile["allergies"] == [] and profile["clinic"]["name"] is None

    def test_blank_values_are_not_filled_in(self, client, mock_db, regular_user_token, test_pet):
        _put(
            client,
            regular_user_token,
            test_pet,
            {
                "chip_number": "   ",
                "allergies": [{"substance": "  Курица  ", "reaction": ""}],
                "clinic": {"phone": "  "},
            },
        )
        profile = _card(client, regular_user_token, test_pet)["profile"]
        assert profile["chip_number"] is None and profile["clinic"]["phone"] is None
        assert profile["allergies"] == [{"substance": "Курица", "reaction": None}]

    def test_no_allergies_known_is_different_from_not_filled_in(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, {"allergies_none_known": True})
        assert _card(client, regular_user_token, test_pet)["profile"]["allergies_none_known"] is True

    @pytest.mark.parametrize(
        "body",
        [
            {"allergies_none_known": True, "allergies": [{"substance": "Курица"}]},
            {"allergies": [{"substance": ""}]},
            {"allergies": [{"substance": "x" * 101}]},
            {"allergies": [{"substance": "x"}] * 31},
            {"conditions": [{"name": "Астма", "since_year": 1800}]},
            {"chip_number": "1" * 31},
            {"clinic": {"phone": "1" * 31}},
        ],
    )
    def test_bad_profiles_are_refused(self, client, regular_user_token, test_pet, body):
        assert _put(client, regular_user_token, test_pet, body).status_code == 422

    def test_saving_the_profile_leaves_the_rest_of_the_pet_alone(self, client, mock_db, regular_user_token, test_pet):
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"health_notes": "Заметка", "breed": "Лабрадор"}})
        _put(client, regular_user_token, test_pet, FULL)
        pet = mock_db["pets"].find_one({"_id": test_pet["_id"]})
        assert (pet["health_notes"], pet["breed"], pet["name"]) == ("Заметка", "Лабрадор", test_pet["name"])

    def test_editing_the_pet_card_leaves_the_profile_alone(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, FULL)
        client.put(f"/api/pets/{test_pet['_id']}", json={"breed": "Другая"}, headers=_auth(regular_user_token))
        assert _card(client, regular_user_token, test_pet)["profile"]["chip_number"] == "643093100123456"

    def test_no_author_is_stored_with_it(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, FULL)
        assert set(mock_db["pets"].find_one({"_id": test_pet["_id"]})["medical_profile"]) == {
            "chip_number",
            "blood_type",
            "allergies",
            "allergies_none_known",
            "conditions",
            "diet",
            "living",
            "reproduction",
            "clinics",
            "clinic",
            "updated_at",
            "version",
        }

    def test_a_broken_stored_profile_does_not_take_the_card_down(self, client, mock_db, regular_user_token, test_pet):
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"medical_profile": {"allergies": "not a list"}}})
        card = _card(client, regular_user_token, test_pet)
        assert card["profile"]["allergies"] == []


@pytest.mark.health
class TestRepeatsAreMerged:
    def test_an_allergen_written_twice_is_one_allergen_with_what_each_said(
        self, client, mock_db, regular_user_token, test_pet
    ):
        body = {
            **FULL,
            "allergies": [
                {"substance": "Курица", "reaction": "зуд"},
                {"substance": "  курица  ", "reaction": "Зуд"},
                {"substance": "КУРИЦА", "reaction": "сыпь"},
                {"substance": "Амоксициллин"},
            ],
        }
        assert _put(client, regular_user_token, test_pet, body).status_code == 200
        allergies = _card(client, regular_user_token, test_pet)["profile"]["allergies"]
        assert [(a["substance"], a["reaction"]) for a in allergies] == [("Курица", "зуд, сыпь"), ("Амоксициллин", None)]

    def test_a_condition_written_twice_is_one_with_the_earliest_year_and_both_notes(
        self, client, mock_db, regular_user_token, test_pet
    ):
        body = {
            **FULL,
            "conditions": [
                {"name": "Гастрит", "since_year": 2024, "note": "осенью"},
                {"name": "гастрит", "since_year": 2022, "note": "диета"},
                {"name": "Дисплазия"},
            ],
        }
        assert _put(client, regular_user_token, test_pet, body).status_code == 200
        conditions = _card(client, regular_user_token, test_pet)["profile"]["conditions"]
        assert [(c["name"], c["since_year"], c["note"]) for c in conditions] == [
            ("Гастрит", 2022, "осенью; диета"),
            ("Дисплазия", None, None),
        ]

    def test_the_joined_reaction_stays_within_its_length(self, client, mock_db, regular_user_token, test_pet):
        body = {
            **FULL,
            "allergies": [{"substance": "Корм", "reaction": "а" * 150}, {"substance": "корм", "reaction": "б" * 150}],
        }
        assert _put(client, regular_user_token, test_pet, body).status_code == 200
        reaction = _card(client, regular_user_token, test_pet)["profile"]["allergies"][0]["reaction"]
        assert len(reaction) <= 200 and reaction.startswith("а" * 150)

    def test_different_allergens_are_all_kept(self, client, mock_db, regular_user_token, test_pet):
        body = {**FULL, "allergies": [{"substance": "Курица"}, {"substance": "Курица в соусе"}, {"substance": "Рыба"}]}
        assert _put(client, regular_user_token, test_pet, body).status_code == 200
        names = [a["substance"] for a in _card(client, regular_user_token, test_pet)["profile"]["allergies"]]
        assert names == ["Курица", "Курица в соусе", "Рыба"]


@pytest.mark.health
class TestWhoMayEditIt:
    def _member(self, mock_db, pet, name="friend"):
        mock_db["users"].insert_one({"username": name, "is_active": True, "password_hash": "x"})
        mock_db["pets"].update_one({"_id": pet["_id"]}, {"$set": {"shared_with": [name]}})
        return create_access_token(name)

    def test_a_shared_user_may_edit_the_profile_though_not_the_pet_card(
        self, client, mock_db, regular_user_token, test_pet
    ):
        token = self._member(mock_db, test_pet)
        assert _put(client, token, test_pet, FULL).status_code == 200
        assert client.put(f"/api/pets/{test_pet['_id']}", json={"breed": "x"}, headers=_auth(token)).status_code == 403
        assert _card(client, regular_user_token, test_pet)["profile"]["blood_type"] == "A"

    def test_a_stranger_may_not(self, client, mock_db, test_pet):
        mock_db["users"].insert_one({"username": "stranger", "is_active": True, "password_hash": "x"})
        response = _put(client, create_access_token("stranger"), test_pet, FULL)
        assert response.status_code in (403, 404)
        assert "medical_profile" not in mock_db["pets"].find_one({"_id": test_pet["_id"]})

    def test_nobody_without_a_login(self, client, test_pet):
        assert client.put(f"/api/pets/{test_pet['_id']}/medical-profile", json=FULL).status_code == 401


@pytest.mark.health
class TestProfileInThePdf:
    def _text(self, client, token, pet):
        response = client.get(f"/api/pets/{pet['_id']}/medical-card/pdf", headers=_auth(token))
        assert response.status_code == 200
        # a long line wraps: the text is read on one line
        return " ".join("\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages).split())

    def test_the_profile_is_on_the_paper(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, FULL)
        text = self._text(client, regular_user_token, test_pet)
        for needle in (
            "Курица: зуд, покраснение ушей",
            "Амоксициллин",
            "Хронический гастрит (с 2024 года): обострения осенью",
            "Группа крови A",
            "чип 643093100123456",
            "Вет-клиника Друг, +7 701 000 00 00. Врач: Иванова А. П.",
        ):
            assert needle in text, needle

    def test_the_three_states_of_allergies_read_differently(self, client, mock_db, regular_user_token, test_pet):
        assert "Аллергии не указаны" in self._text(client, regular_user_token, test_pet)
        _put(client, regular_user_token, test_pet, {"allergies_none_known": True})
        assert "Аллергии не выявлено" in self._text(client, regular_user_token, test_pet)
        _put(client, regular_user_token, test_pet, {"allergies": [{"substance": "Курица"}]})
        text = self._text(client, regular_user_token, test_pet)
        assert "Аллергия Курица" in text and "не выявлено" not in text


TWO_CLINICS = {
    "clinics": [
        {
            "name": "Друг",
            "phone": "+7 701 000 00 00",
            "doctors": [
                {"name": "Иванова А. П.", "specialty": "терапевт"},
                {"name": "Петров", "specialty": "кардиолог"},
            ],
        },
        {"name": "Зубастик", "phone": "+7 702 111 11 11", "doctors": [{"name": "Сидорова", "specialty": "стоматолог"}]},
    ]
}


@pytest.mark.health
class TestSeveralClinicsAndDoctors:
    """A pet is taken to a general vet, a cardiologist and a dental clinic: each with its doctors and what they do."""

    def test_the_clinics_with_their_doctors_are_saved_and_come_back_in_order(
        self, client, mock_db, regular_user_token, test_pet
    ):
        assert _put(client, regular_user_token, test_pet, TWO_CLINICS).status_code == 200
        profile = _card(client, regular_user_token, test_pet)["profile"]
        assert [c["name"] for c in profile["clinics"]] == ["Друг", "Зубастик"]
        assert [(d["name"], d["specialty"]) for d in profile["clinics"][0]["doctors"]] == [
            ("Иванова А. П.", "терапевт"),
            ("Петров", "кардиолог"),
        ]

    def test_the_main_clinic_is_the_first_one_and_the_single_clinic_field_follows_it(
        self, client, mock_db, regular_user_token, test_pet
    ):
        _put(client, regular_user_token, test_pet, TWO_CLINICS)
        clinic = _card(client, regular_user_token, test_pet)["profile"]["clinic"]
        assert clinic == {"name": "Друг", "vet": "Иванова А. П.", "phone": "+7 701 000 00 00"}

    def test_the_single_clinic_of_an_older_client_becomes_the_first_entry(
        self, client, mock_db, regular_user_token, test_pet
    ):
        _put(client, regular_user_token, test_pet, FULL)
        (entry,) = _card(client, regular_user_token, test_pet)["profile"]["clinics"]
        assert entry["name"] == "Вет-клиника Друг" and entry["phone"] == "+7 701 000 00 00"
        assert [d["name"] for d in entry["doctors"]] == ["Иванова А. П."]

    def test_a_profile_stored_before_the_list_is_read_as_one_clinic(
        self, client, mock_db, regular_user_token, test_pet
    ):
        mock_db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {"$set": {"medical_profile": {"clinic": {"name": "Старая", "vet": "Врач", "phone": "1"}}}},
        )
        (entry,) = _card(client, regular_user_token, test_pet)["profile"]["clinics"]
        assert (entry["name"], entry["doctors"][0]["name"]) == ("Старая", "Врач")

    def test_removing_all_the_clinics_clears_the_main_one_too(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, TWO_CLINICS)
        _put(client, regular_user_token, test_pet, {"blood_type": "A"})
        profile = _card(client, regular_user_token, test_pet)["profile"]
        assert profile["clinics"] == [] and profile["clinic"]["name"] is None

    @pytest.mark.parametrize(
        "body",
        [
            {"clinics": [{"name": f"К{i}"} for i in range(6)]},
            {"clinics": [{"name": "К", "doctors": [{"name": f"В{i}"} for i in range(11)]}]},
            {"clinics": [{"name": "К", "doctors": [{"name": ""}]}]},
            {"clinics": [{"name": "К", "doctors": [{"name": "В", "specialty": "x" * 61}]}]},
            {"clinics": [{"name": "к" * 101}]},
        ],
    )
    def test_the_limits(self, client, regular_user_token, test_pet, body):
        assert _put(client, regular_user_token, test_pet, body).status_code == 422

    def test_the_pdf_names_every_clinic_with_its_doctors_and_what_they_do(
        self, client, mock_db, regular_user_token, test_pet
    ):
        _put(client, regular_user_token, test_pet, TWO_CLINICS)
        response = client.get(f"/api/pets/{test_pet['_id']}/medical-card/pdf", headers=_auth(regular_user_token))
        text = " ".join("\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages).split())
        assert "Друг, +7 701 000 00 00. Врачи: Иванова А. П., терапевт; Петров, кардиолог" in text
        assert "Зубастик, +7 702 111 11 11. Врач: Сидорова, стоматолог" in text

    def test_with_several_clinics_a_record_says_which_one_it_was_with_one_it_does_not_repeat_it(
        self, client, mock_db, regular_user_token, test_pet
    ):
        pid = str(test_pet["_id"])
        mock_db["medical_records"].insert_one(
            {
                "pet_id": pid,
                "kind": "visit",
                "title": "Осмотр зубов",
                "date": "2024-03-01",
                "clinic": "Зубастик",
                "vet": "Сидорова",
            }
        )

        def text():
            response = client.get(f"/api/pets/{pid}/medical-card/pdf", headers=_auth(regular_user_token))
            return " ".join("\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages).split())

        _put(client, regular_user_token, test_pet, TWO_CLINICS)
        assert "Осмотр зубов Зубастик, врач Сидорова" in text()
        _put(
            client, regular_user_token, test_pet, {"clinics": [{"name": "Зубастик", "doctors": [{"name": "Сидорова"}]}]}
        )
        assert "Осмотр зубов Зубастик, врач Сидорова" not in text()


@pytest.mark.health
class TestTwoPeopleEditingTheProfile:
    """The form is made from a version of the profile. Saving that copy after someone else saved would wipe their
    allergy without a word, so the server compares versions and says so."""

    def test_every_save_carries_a_new_version(self, client, mock_db, regular_user_token, test_pet):
        first = _put(client, regular_user_token, test_pet, FULL).get_json()["profile"]
        second = _put(client, regular_user_token, test_pet, FULL).get_json()["profile"]
        assert first["version"] and second["version"] and first["version"] != second["version"]
        assert _card(client, regular_user_token, test_pet)["profile"]["version"] == second["version"]

    def test_a_save_from_the_current_version_goes_through(self, client, mock_db, regular_user_token, test_pet):
        version = _put(client, regular_user_token, test_pet, FULL).get_json()["profile"]["version"]
        response = _put(client, regular_user_token, test_pet, {**FULL, "blood_type": "B", "base_version": version})
        assert response.status_code == 200
        assert response.get_json()["profile"]["blood_type"] == "B"

    def test_a_stale_copy_is_refused_and_the_other_persons_work_stays(
        self, client, mock_db, regular_user_token, test_pet
    ):
        opened = _put(client, regular_user_token, test_pet, FULL).get_json()["profile"]["version"]
        # Someone else adds an allergy after this form was opened.
        theirs = {**FULL, "allergies": [*FULL["allergies"], {"substance": "Рыба"}], "base_version": opened}
        assert _put(client, regular_user_token, test_pet, theirs).status_code == 200
        # The first form, still on the old version, saves a change to the chip.
        response = _put(client, regular_user_token, test_pet, {**FULL, "chip_number": "111", "base_version": opened})
        assert response.status_code == 409
        body = response.get_json()
        assert body["code"] == "conflict"
        assert [a["substance"] for a in body["profile"]["allergies"]] == ["Курица", "Амоксициллин", "Рыба"]
        stored = _card(client, regular_user_token, test_pet)["profile"]
        assert stored["chip_number"] == "643093100123456" and len(stored["allergies"]) == 3

    def test_a_client_that_sends_no_version_still_saves_as_before(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, FULL)
        assert _put(client, regular_user_token, test_pet, {**FULL, "blood_type": "C"}).status_code == 200

    def test_a_form_made_from_an_unsaved_profile_is_stale_once_someone_saves(
        self, client, mock_db, regular_user_token, test_pet
    ):
        # Both forms opened on a profile with nothing in it (no version, sent as an empty string).
        assert _put(client, regular_user_token, test_pet, {**FULL, "base_version": ""}).status_code == 200
        second = _put(client, regular_user_token, test_pet, {**FULL, "blood_type": "B", "base_version": ""})
        assert second.status_code == 409
        assert second.get_json()["profile"]["blood_type"] == "A"

    def test_a_profile_saved_before_versions_existed_takes_a_form_made_from_it(
        self, client, mock_db, regular_user_token, test_pet
    ):
        mock_db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {"$set": {"medical_profile": {"chip_number": "1", "updated_at": "2026-01-01 10:00"}}},
        )
        assert _put(client, regular_user_token, test_pet, {**FULL, "base_version": ""}).status_code == 200
