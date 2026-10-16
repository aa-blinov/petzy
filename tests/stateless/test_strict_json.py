"""Request JSON is read without NaN and Infinity, the same way for a plain body, a gzip body and a JSON part of a form."""

import gzip

import pytest
from flask_pydantic_spec import flask_backend

from web.pydantic_helpers import form_value
from web.strict_json import NonFiniteNumber, loads

NOT_FINITE = "Числа NaN и Infinity не принимаются"


@pytest.mark.parametrize("text", ['{"x": NaN}', '{"x": Infinity}', '{"x": -Infinity}', '{"x": 1e400}', "[-1e400]"])
def test_the_reader_refuses_a_number_that_is_not_finite(text):
    with pytest.raises(NonFiniteNumber):
        loads(text)


def test_ordinary_numbers_and_the_words_nan_and_infinity_read_as_before():
    assert loads('{"a": 1.5, "b": -2, "c": 1e3, "d": "NaN", "e": "Infinity"}') == {
        "a": 1.5,
        "b": -2,
        "c": 1000.0,
        "d": "NaN",
        "e": "Infinity",
    }


def test_a_json_part_of_a_form_is_read_strictly_and_text_stays_text():
    with pytest.raises(NonFiniteNumber):
        form_value(['{"x": NaN}'])
    assert form_value(['{"x": 1}']) == {"x": 1}
    assert form_value(["7"]) == "7"


def test_the_library_reads_its_own_json_strictly():
    with pytest.raises(NonFiniteNumber):
        flask_backend.json.loads('{"x": NaN}')
    assert flask_backend.json.loads('{"x": 1}') == {"x": 1}


def test_a_gzip_body_with_infinity_is_refused(client, regular_user_token, test_pet):
    body = gzip.compress('{"frame": "heart", "crops": {"heart": {"x": Infinity, "y": 5, "w": 60, "h": 60}}}'.encode())

    response = client.put(
        f"/api/pets/{test_pet['_id']}/look",
        data=body,
        content_type="application/json",
        headers={"Authorization": f"Bearer {regular_user_token}", "Content-Encoding": "gzip"},
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == NOT_FINITE


def test_a_gzip_body_without_infinity_is_still_read(client, regular_user_token, test_pet):
    body = gzip.compress('{"tagline": "Хозяин дивана"}'.encode())

    response = client.put(
        f"/api/pets/{test_pet['_id']}/look",
        data=body,
        content_type="application/json",
        headers={"Authorization": f"Bearer {regular_user_token}", "Content-Encoding": "gzip"},
    )

    assert response.status_code == 200
    assert response.get_json()["look"]["tagline"] == "Хозяин дивана"
