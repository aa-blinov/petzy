"""The answers a refused request gives: the words for the person, the details for the code (web/validation.py).

Every refusal answers in one shape: ``error`` for the person, ``details`` for the code. The words are
Russian, and the edge of a rule is where a person reads them
"""

import json

import pytest
from flask import Response

from web.validation import before_request_validation, details_for, message_for


class TestTheWordsForThePerson:
    @pytest.mark.parametrize(
        "error, expected",
        [
            # A date that cannot be read says which thing to check.
            ({"type": "date_from_datetime_parsing"}, "Проверьте дату и время"),
            ({"type": "datetime_parsing"}, "Проверьте дату и время"),
            # A switch that cannot be read says so.
            ({"type": "bool_parsing"}, "Неверное значение переключателя"),
            ({"type": "bool_type"}, "Неверное значение переключателя"),
            # A text too short says how short it may not be.
            ({"type": "string_too_short", "ctx": {"min_length": 3}}, "Слишком короткий текст: не меньше 3 символов"),
        ],
    )
    def test_the_message(self, error, expected):
        assert message_for([error]) == expected

    def test_a_limit_that_cannot_be_read_as_a_number_still_answers(self):
        """The word for the count never depends on the count being readable: a limit that is not a number
        gets the general word, and the answer still comes."""
        assert (
            message_for([{"type": "string_too_long", "ctx": {"max_length": "много"}}])
            == "Слишком длинный текст: не больше много символов"
        )


class TestTheDetailsForTheCode:
    def test_a_detail_names_the_field_and_the_rule(self):
        assert details_for([{"type": "missing", "loc": ("body", "name")}]) == [{"field": "name", "type": "missing"}]

    def test_an_error_that_is_not_a_rule_is_left_out(self):
        """Only the rules the code can act on are listed: anything else is not a detail."""
        assert details_for(["not a rule", {"type": "missing", "loc": ("body", "name")}]) == [
            {"field": "name", "type": "missing"}
        ]


class TestTheAnswerToARefusedRequest:
    def test_a_refusal_the_code_cannot_read_still_answers_in_the_usual_shape(self):
        """The raw error list of the library is not always readable: the answer is still the usual one,
        so the person is told what to do and the code is told the kind of failure."""

        class Unreadable:
            def json(self):
                raise ValueError("the list is not json")

        resp = Response()
        before_request_validation(None, resp, Unreadable(), None)

        body = json.loads(resp.get_data(as_text=True))
        assert body == {
            "success": False,
            "error": "Проверьте введённые данные",
            "code": "validation_error",
            "details": [],
        }
        assert resp.mimetype == "application/json"
