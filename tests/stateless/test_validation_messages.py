"""A request that fails validation answers in Russian, in the usual error shape."""

import pytest

from web.validation import message_for


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_too_long_text_says_the_limit(client, regular_user_token, test_pet):
    response = client.post(
        "/api/events",
        json={
            "pet_id": str(test_pet["_id"]),
            "type": "feeding",
            "date": "2026-01-01",
            "time": "10:00",
            "comment": "к" * 600,
        },
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422
    body = response.get_json()
    assert body["success"] is False and body["code"] == "validation_error"
    assert body["error"] == "Слишком длинный текст: не больше 500 символов"
    assert body["details"] == [{"field": "comment", "type": "string_too_long"}]


def test_a_multipart_form_says_it_in_russian_too(client, regular_user_token):
    response = client.post(
        "/api/pets",
        data={"name": "Я" * 150, "species": "cat"},
        headers=_auth(regular_user_token),
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert response.get_json()["error"] == "Слишком длинный текст: не больше 100 символов"


@pytest.mark.parametrize(
    "error, expected",
    [
        ({"type": "missing"}, "Заполните обязательные поля"),
        ({"type": "string_too_short", "ctx": {"min_length": 1}}, "Заполните обязательные поля"),
        ({"type": "string_too_long", "ctx": {"max_length": 1}}, "Слишком длинный текст: не больше 1 символа"),
        ({"type": "float_parsing"}, "Введите число"),
        ({"type": "less_than_equal", "ctx": {"le": 100}}, "Число вне допустимых пределов (100)"),
        ({"type": "value_error", "msg": "Value error, Дата не может быть в будущем"}, "Дата не может быть в будущем"),
        ({"type": "something_new", "msg": "Some English"}, "Проверьте введённые данные"),
    ],
)
def test_messages(error, expected):
    assert message_for([error]) == expected
