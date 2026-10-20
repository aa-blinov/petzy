"""The name a device gives a record it made offline, and the access check of such a record (web/offline.py).

``clean_local_id`` is the name as the device sent it: the spaces around it go, an empty one names nothing.
``require_local_record_access`` is the check of a record the device names instead of an id: a request that
cannot say who it is is refused before any record is read
"""

import pytest

from web import offline


class TestTheNameADeviceGives:
    def test_no_name_stays_no_name(self):
        assert offline.clean_local_id(None) is None

    def test_the_spaces_around_it_go(self):
        assert offline.clean_local_id("  n1  ") == "n1"

    def test_an_empty_name_names_nothing(self):
        with pytest.raises(ValueError):
            offline.clean_local_id("")

    def test_a_name_of_spaces_names_nothing(self):
        with pytest.raises(ValueError):
            offline.clean_local_id("   ")


class TestTheAccessCheckOfARecordNamedByItsName:
    def test_a_request_that_cannot_say_who_it_is_answers_401_and_looks_at_no_record(self, monkeypatch):
        """The check reads who is asking before it reads anything: a request without a name for the person
        is refused, and no record of anybody is read."""
        from web.app import app as flask_app
        from web.errors import error_response

        monkeypatch.setattr(offline, "login_required", lambda view: view)
        monkeypatch.setattr(offline, "get_current_user", lambda: (None, error_response("unauthorized")))

        asked = []

        @offline.require_local_record_access("events", "event")
        def view(local_id):
            asked.append(local_id)
            return "ok"

        with flask_app.test_request_context("/api/events/local/n1", method="PUT"):
            answer = view(local_id="n1")

        assert answer[1] == 401
        assert asked == []
