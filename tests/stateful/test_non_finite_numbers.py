"""A number that is not finite, and a flag where a number belongs, is refused, and nothing is written.

NaN and Infinity are not JSON numbers, and a client can also send them as text («inf»). A field with no bound of its
own took them: a dose of Infinity drew the whole stock down (min(stock, Infinity) is the stock). Each case checks the
answer and that the database did not change. true and false are not numbers either: a float reads them as 1 and 0.
"""

import json

import pytest

NOT_FINITE = "Числа NaN и Infinity не принимаются"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _raw(client, method, url, text, token):
    """The body as it is written, so NaN and Infinity reach the server as literals (json= cannot send them)."""
    return client.open(url, method=method, data=text, content_type="application/json", headers=_auth(token))


def _no_constants(name):
    raise ValueError(f"not JSON: {name}")


@pytest.fixture
def number_type(client, regular_user_token):
    """A custom type with one number field. Its field gets min 0 and no max, so only the finiteness check refuses it."""
    response = client.post(
        "/api/event-types",
        json={
            "label": "Замер",
            "icon": "paw",
            "color": "green",
            "fields": [{"name": "n", "label": "Число", "type": "number"}],
        },
        headers=_auth(regular_user_token),
    )
    return response.get_json()["key"]


def _record_text(pet_id, type_key, fields):
    """A record as JSON text, with the fields written as they are (NaN, "inf", ...)."""
    return f'{{"pet_id": "{pet_id}", "type": "{type_key}", "date": "2026-01-01", "time": "10:00", "tz": "Asia/Almaty", "fields": {fields}}}'


class TestEventNumbers:
    def test_nan_in_a_number_field_is_refused_and_nothing_is_saved(
        self, client, mock_db, regular_user_token, test_pet, number_type
    ):
        text = _record_text(test_pet["_id"], number_type, '{"n": NaN}')

        response = _raw(client, "post", "/api/events", text, regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == NOT_FINITE
        assert mock_db["events"].count_documents({}) == 0

    def test_nan_under_a_key_the_type_does_not_declare_is_refused_too(
        self, client, mock_db, regular_user_token, test_pet, number_type
    ):
        # An undeclared key is dropped without a look, so only the reader sees the NaN in it.
        text = _record_text(test_pet["_id"], number_type, '{"n": 1, "unused": NaN}')

        response = _raw(client, "post", "/api/events", text, regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == NOT_FINITE
        assert mock_db["events"].count_documents({}) == 0

    @pytest.mark.parametrize("value", ['"inf"', '"-inf"', '"nan"', '"Infinity"'])
    def test_text_that_reads_as_infinity_is_not_a_number(
        self, client, mock_db, regular_user_token, test_pet, number_type, value
    ):
        text = _record_text(test_pet["_id"], number_type, f'{{"n": {value}}}')

        response = _raw(client, "post", "/api/events", text, regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == "Поле «Число» должно быть числом"
        assert mock_db["events"].count_documents({}) == 0

    def test_a_number_too_large_for_a_float_is_refused_not_a_server_error(
        self, client, mock_db, regular_user_token, test_pet, number_type
    ):
        text = _record_text(test_pet["_id"], number_type, f'{{"n": {10**400}}}')

        response = _raw(client, "post", "/api/events", text, regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == "Поле «Число» должно быть числом"
        assert mock_db["events"].count_documents({}) == 0

    @pytest.mark.parametrize("value", ["true", "false"])
    def test_a_flag_in_a_number_field_is_refused_not_read_as_one_or_zero(
        self, client, mock_db, regular_user_token, test_pet, number_type, value
    ):
        text = _record_text(test_pet["_id"], number_type, f'{{"n": {value}}}')

        response = _raw(client, "post", "/api/events", text, regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == "Поле «Число» должно быть числом"
        assert mock_db["events"].count_documents({}) == 0


class TestEventTypeBounds:
    def test_a_bound_given_as_text_infinity_is_refused(self, client, mock_db, regular_user_token):
        before = mock_db["event_types"].count_documents({})

        response = client.post(
            "/api/event-types",
            json={
                "label": "Замер",
                "icon": "paw",
                "color": "green",
                "fields": [{"name": "n", "label": "Число", "type": "number", "max": "inf"}],
            },
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 422
        assert response.get_json()["error"] == "Введите число"
        assert mock_db["event_types"].count_documents({}) == before

    def test_a_bound_that_is_nan_is_refused(self, client, mock_db, regular_user_token):
        before = mock_db["event_types"].count_documents({})
        text = (
            '{"label": "Замер", "icon": "paw", "color": "green", '
            '"fields": [{"name": "n", "label": "Число", "type": "number", "max": NaN}]}'
        )

        response = _raw(client, "post", "/api/event-types", text, regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == NOT_FINITE
        assert mock_db["event_types"].count_documents({}) == before


@pytest.fixture
def course(mock_db, test_pet):
    """A course with a stock of 12 and two doses a day."""
    doc = {
        "name": "Габапентин",
        "type": "Капсула",
        "pet_id": str(test_pet["_id"]),
        "default_dose": 1.0,
        "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00", "20:00"]},
        "inventory_enabled": True,
        "inventory_current": 12.0,
        "is_active": True,
        "username": "testuser",
    }
    return mock_db["medications"].insert_one(doc).inserted_id


def _stock(mock_db, course_id):
    return mock_db["medications"].find_one({"_id": course_id})["inventory_current"]


def _intake_text(dose):
    return f'{{"date": "2026-01-01", "time": "10:00", "dose_taken": {dose}}}'


class TestDoseAndStock:
    def test_an_infinite_dose_cannot_empty_the_stock(self, client, mock_db, regular_user_token, course):
        response = _raw(client, "post", f"/api/medications/{course}/log", _intake_text("Infinity"), regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == NOT_FINITE
        assert _stock(mock_db, course) == 12.0
        assert mock_db["medication_intakes"].count_documents({}) == 0

    def test_a_dose_given_as_text_infinity_is_refused(self, client, mock_db, regular_user_token, course):
        response = _raw(client, "post", f"/api/medications/{course}/log", _intake_text('"inf"'), regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == "Введите число"
        assert _stock(mock_db, course) == 12.0
        assert mock_db["medication_intakes"].count_documents({}) == 0

    def test_a_nan_dose_is_refused(self, client, mock_db, regular_user_token, course):
        response = _raw(client, "post", f"/api/medications/{course}/log", _intake_text("NaN"), regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == NOT_FINITE
        assert _stock(mock_db, course) == 12.0
        assert mock_db["medication_intakes"].count_documents({}) == 0

    def test_restock_refuses_an_infinite_amount(self, client, mock_db, regular_user_token, course):
        response = _raw(
            client, "post", f"/api/medications/{course}/restock", '{"amount": Infinity}', regular_user_token
        )

        assert response.status_code == 422
        assert response.get_json()["error"] == NOT_FINITE
        assert _stock(mock_db, course) == 12.0

    def test_the_stock_cannot_be_set_to_infinity(self, client, mock_db, regular_user_token, course):
        response = _raw(
            client, "put", f"/api/medications/{course}", '{"inventory_current": Infinity}', regular_user_token
        )

        assert response.status_code == 422
        assert response.get_json()["error"] == NOT_FINITE
        assert _stock(mock_db, course) == 12.0

    def test_the_stock_cannot_be_set_to_text_infinity(self, client, mock_db, regular_user_token, course):
        response = _raw(client, "put", f"/api/medications/{course}", '{"inventory_current": "inf"}', regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == "Введите число"
        assert _stock(mock_db, course) == 12.0

    def test_an_answer_with_a_normal_number_is_strict_json(self, client, mock_db, regular_user_token, course):
        response = client.post(
            f"/api/medications/{course}/restock", json={"amount": 30}, headers=_auth(regular_user_token)
        )

        assert response.status_code == 200
        assert json.loads(response.data, parse_constant=_no_constants)["inventory_current"] == 42.0

    @pytest.mark.parametrize("value", ["true", "false"])
    def test_a_flag_as_the_dose_is_refused(self, client, mock_db, regular_user_token, course, value):
        response = _raw(client, "post", f"/api/medications/{course}/log", _intake_text(value), regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == "Значение должно быть числом"
        assert _stock(mock_db, course) == 12.0
        assert mock_db["medication_intakes"].count_documents({}) == 0

    def test_a_flag_as_the_stock_is_refused(self, client, mock_db, regular_user_token, course):
        response = _raw(client, "put", f"/api/medications/{course}", '{"inventory_current": true}', regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == "Значение должно быть числом"
        assert _stock(mock_db, course) == 12.0


class TestPetLookCrops:
    def test_a_crop_with_nan_is_refused_and_not_saved(self, client, mock_db, regular_user_token, test_pet):
        text = '{"frame": "heart", "crops": {"heart": {"x": NaN, "y": 5, "w": 60, "h": 60}}}'

        response = _raw(client, "put", f"/api/pets/{test_pet['_id']}/look", text, regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == NOT_FINITE
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}).get("look") is None

    def test_a_crop_given_as_text_is_refused_in_words_about_the_photo(
        self, client, mock_db, regular_user_token, test_pet
    ):
        text = '{"frame": "heart", "crops": {"heart": {"x": "inf", "y": 5, "w": 60, "h": 60}}}'

        response = _raw(client, "put", f"/api/pets/{test_pet['_id']}/look", text, regular_user_token)

        assert response.status_code == 422
        assert response.get_json()["error"] == "Введите числа для области фото"
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}).get("look") is None
