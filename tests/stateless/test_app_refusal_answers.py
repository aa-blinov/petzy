"""What the app answers when a request is refused: the same text and the same shape every time.

The two handlers here are the last word of the API: the 422 of a failed check and the 429 of a
spent limit. A person reads both, so the words in them matter: how long to wait, and what was
wrong with the request. A limit of a few minutes says how many minutes, a limit of an hour says an
hour, and a limit the server cannot measure still answers, without a time it does not know.
"""

from flask import Flask

from web.app import handle_rate_limit_exceeded, handle_unprocessable_entity


class _FakeError(Exception):
    def __init__(self, data):
        super().__init__("validation failed")
        self.data = data


class _FakeLimit:
    """A limit as the limiter hands it over: the window in seconds."""

    def __init__(self, expiry):
        self.limit = self
        self._expiry = expiry

    def get_expiry(self):
        if isinstance(self._expiry, Exception):
            raise self._expiry
        return self._expiry


class _FakeRateLimit(Exception):
    def __init__(self, expiry):
        super().__init__("rate limit exceeded")
        self.limit = _FakeLimit(expiry)


def _answer(data):
    app = Flask(__name__)
    with app.test_request_context("/"):
        body, status = handle_unprocessable_entity(_FakeError(data))
        return body.get_json(), status


def test_a_check_that_failed_without_a_list_of_problems_answers_in_general():
    """Nothing to point at: the answer says the data are wrong, and nothing more."""
    body, status = _answer({"messages": {"date": "wrong"}})

    assert status == 422
    assert body["code"] == "validation_error"
    assert body["error"] == "Проверьте введённые данные"


def test_an_empty_list_of_problems_answers_in_general():
    body, status = _answer({"messages": []})

    assert status == 422
    assert body["code"] == "validation_error"
    assert body["error"] == "Проверьте введённые данные"


def test_the_problem_of_a_field_is_answered_as_it_is():
    """The text of the check is passed on as it is, without any prefix."""
    body, status = _answer({"messages": [{"loc": ["body", "date"], "msg": "Некорректная дата", "type": "value_error"}]})

    assert status == 422
    assert body["error"] == "Некорректная дата"


def _rate_answer(expiry):
    app = Flask(__name__)
    with app.test_request_context("/"):
        response, status = handle_rate_limit_exceeded(_FakeRateLimit(expiry))
        return response.get_json(), status


def test_a_limit_of_a_few_minutes_says_how_many():
    body, status = _rate_answer(300)

    assert status == 429
    assert body["error"] == "Слишком много попыток с этого адреса. Попробуйте через 5 мин"
    assert body["retry_after"] == 300


def test_a_limit_of_an_hour_says_an_hour():
    body, _ = _rate_answer(3600)

    assert body["error"] == "Слишком много попыток с этого адреса. Попробуйте через час"


def test_a_limit_the_server_cannot_measure_still_answers():
    """An unusual limit object must not take the answer away: only the time it does not know."""
    body, status = _rate_answer(RuntimeError("no window here"))

    assert status == 429
    assert body["code"] == "rate_limit_exceeded"
    assert "retry_after" not in body
