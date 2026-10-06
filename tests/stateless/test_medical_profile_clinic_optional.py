"""The single `clinic` of the older profile: the app does not send it any more.

`clinics` is the truth of the list; the server fills the old field itself so that the PDF header and a cached app keep
seeing the main clinic. These tests say what that means from the outside: a save without the field is accepted, and the
main clinic still lands on the card and on the paper. If `clinic` ever becomes required again, the first test fails.
"""

import io

import pytest
from pypdf import PdfReader


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


_WITHOUT_LEGACY = {
    "chip_number": "643093100123456",
    "blood_type": "A",
    "allergies": [],
    "allergies_none_known": True,
    "conditions": [],
    "clinics": [
        {
            "name": "Вет-клиника Друг",
            "phone": "+7 701 000 00 00",
            "doctors": [{"name": "Иванова А. П.", "specialty": "Терапевт"}],
        }
    ],
}


def _put(client, token, pet, body):
    return client.put(f"/api/pets/{pet['_id']}/medical-profile", json=body, headers=_auth(token))


def _profile(client, token, pet):
    card = client.get(f"/api/pets/{pet['_id']}/medical-card", headers=_auth(token)).get_json()["card"]
    return card["profile"]


@pytest.mark.health
class TestTheProfileWithoutTheLegacyClinic:
    def test_it_is_accepted_and_saved(self, client, mock_db, regular_user_token, test_pet):
        response = _put(client, regular_user_token, test_pet, _WITHOUT_LEGACY)
        assert response.status_code == 200
        profile = _profile(client, regular_user_token, test_pet)
        assert [c["name"] for c in profile["clinics"]] == ["Вет-клиника Друг"]

    def test_the_main_clinic_is_kept_for_what_reads_the_old_field(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, _WITHOUT_LEGACY)
        stored = mock_db["pets"].find_one({"_id": test_pet["_id"]})["medical_profile"]
        assert stored["clinic"]["name"] == "Вет-клиника Друг"

    def test_the_paper_names_the_clinic(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, _WITHOUT_LEGACY)
        response = client.get(f"/api/pets/{test_pet['_id']}/medical-card/pdf", headers=_auth(regular_user_token))
        assert response.status_code == 200
        text = " ".join("\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages).split())
        assert "Вет-клиника Друг, +7 701 000 00 00. Врач: Иванова А. П." in text

    def test_an_older_client_that_still_sends_it_is_understood(self, client, mock_db, regular_user_token, test_pet):
        body = dict(_WITHOUT_LEGACY)
        body["clinic"] = {"name": "Старая клиника", "vet": "Петров В. В.", "phone": None}
        assert _put(client, regular_user_token, test_pet, body).status_code == 200
        assert [c["name"] for c in _profile(client, regular_user_token, test_pet)["clinics"]] == ["Вет-клиника Друг"]

    def test_the_only_clinic_of_an_older_profile_is_not_lost(self, client, mock_db, regular_user_token, test_pet):
        """A profile stored before the list existed: the single clinic still reaches the card."""
        mock_db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {"$set": {"medical_profile": {"clinic": {"name": "Старая клиника", "vet": "Петров В. В."}}}},
        )
        profile = _profile(client, regular_user_token, test_pet)
        assert [c["name"] for c in profile["clinics"]] == ["Старая клиника"]
