"""Tests for get_message's fallback paths — the happy path (known key,
correct kwargs) is already exercised indirectly by every route that
calls it; these cover the two defensive branches that aren't."""

import pytest


@pytest.mark.unit
class TestGetMessageFallbacks:
    def test_unknown_key_returns_generic_success_message(self):
        from flask import Flask
        from web.messages import get_message

        app = Flask(__name__)
        with app.test_request_context("/"):
            response, status = get_message("this_key_does_not_exist")
            body = response.get_json()

        assert status == 200
        assert body["success"] is True
        assert "this_key_does_not_exist" in body["message"]

    def test_missing_placeholder_kwarg_leaves_message_unformatted(self):
        """pet_shared's template needs `username` — passing some *other*
        kwarg (so the format() call actually runs, unlike passing none
        at all) but not that one must not crash the response, just
        leave the placeholder unfilled."""
        from flask import Flask
        from web.messages import get_message

        app = Flask(__name__)
        with app.test_request_context("/"):
            response, status = get_message("pet_shared", unrelated_kwarg="x")
            body = response.get_json()

        assert status == 200
        assert body["message"] == "Приглашение отправлено пользователю {username}"


def test_user_texts_keep_to_the_product_voice():
    """No field names, no «token», no «курс» for the medicine, no «обновлён»: one dictionary for every text."""
    import re

    from web.errors import ERRORS
    from web.messages import MESSAGES

    texts = [e.message for e in ERRORS.values()] + [m.message for m in MESSAGES.values()]
    banned = [
        r"refresh token",
        r"[Тт]окен",
        r"pet_id",
        r"record_id",
        r"Имя пользователя",
        r"учётн",
        r"[Уу]ведомлен",
        r"обновл[её]н[аоы]?\b",
        r"^Курс ",
    ]
    for text in texts:
        for pattern in banned:
            assert not re.search(pattern, text), (pattern, text)


def test_generic_errors_and_success_texts_are_in_the_dictionary():
    from web.errors import ERRORS
    from web.messages import MESSAGES

    assert ERRORS["validation_error"].message == "Проверьте введённые данные"
    assert ERRORS["internal_error"].message == "Что-то пошло не так, попробуйте позже"
    assert ERRORS["not_found"].message == "Не найдено"
    assert ERRORS["unauthorized_refresh_token_invalid"].message == "Сессия закончилась. Войдите заново"
    assert MESSAGES["medication_created"].message == "Лекарство добавлено"
    assert MESSAGES["medication_deleted"].message == "Лекарство и его приёмы удалены"
    assert MESSAGES["pet_updated"].message == "Питомец сохранён"
    assert MESSAGES["push_subscribed"].message == "Напоминания включены"
    assert MESSAGES["user_password_reset"].message == "Пароль изменён"
