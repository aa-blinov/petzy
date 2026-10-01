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
            "clinic",
            "updated_at",
        }

    def test_a_broken_stored_profile_does_not_take_the_card_down(self, client, mock_db, regular_user_token, test_pet):
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"medical_profile": {"allergies": "not a list"}}})
        card = _card(client, regular_user_token, test_pet)
        assert card["profile"]["allergies"] == []


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
            "Вет-клиника Друг, врач Иванова А. П., +7 701 000 00 00",
        ):
            assert needle in text, needle

    def test_the_three_states_of_allergies_read_differently(self, client, mock_db, regular_user_token, test_pet):
        assert "Аллергии не указаны" in self._text(client, regular_user_token, test_pet)
        _put(client, regular_user_token, test_pet, {"allergies_none_known": True})
        assert "Аллергии не выявлено" in self._text(client, regular_user_token, test_pet)
        _put(client, regular_user_token, test_pet, {"allergies": [{"substance": "Курица"}]})
        text = self._text(client, regular_user_token, test_pet)
        assert "Аллергия Курица" in text and "не выявлено" not in text
