"""What goes to Sentry is scrubbed everywhere, not only in the request body.

An event carries more than the request: the crash's stack (with the local variables of every frame),
the threads that were running, the breadcrumbs of what happened before, and the request itself with
its own address. Every one of those places can hold a password, a token or the secret of a card
link, and each of them has to be cleaned before the event leaves the server.
"""

from web.observability import FILTERED, scrub_event


def test_the_variables_of_a_frame_without_any_are_left_alone():
    """Sentry sends frames without variables when local variables are switched off."""
    event = {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {"filename": "web/auth.py", "lineno": 12},
                            {"filename": "web/auth.py", "lineno": 30, "vars": {"password": "p"}},
                        ]
                    }
                }
            ]
        }
    }

    scrubbed = scrub_event(event)

    frames = scrubbed["exception"]["values"][0]["stacktrace"]["frames"]
    assert frames[0] == {"filename": "web/auth.py", "lineno": 12}
    assert frames[1]["vars"]["password"] == FILTERED


def test_the_variables_of_the_threads_are_scrubbed_too():
    """A crash takes the other threads with it, and their frames hold the same secrets."""
    event = {
        "threads": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {"filename": "web/pets.py", "vars": {"password": "p", "username": "vera"}},
                            {"filename": "web/pets.py"},
                        ]
                    }
                }
            ]
        }
    }

    scrubbed = scrub_event(event)

    frames = scrubbed["threads"]["values"][0]["stacktrace"]["frames"]
    assert frames[0]["vars"] == {"password": FILTERED, "username": "vera"}
    assert frames[1] == {"filename": "web/pets.py"}


def test_a_breadcrumb_without_data_keeps_its_message():
    event = {"breadcrumbs": {"values": [{"message": "navigation"}, {"message": "click on the pet"}]}}

    scrubbed = scrub_event(event)

    assert scrubbed["breadcrumbs"]["values"][0]["message"] == "navigation"
    assert scrubbed["breadcrumbs"]["values"][1]["message"] == "click on the pet"


def test_a_request_without_an_address_keeps_what_it_has():
    event = {"request": {"method": "POST", "headers": {"User-Agent": "Safari"}}}

    scrubbed = scrub_event(event)

    assert scrubbed["request"]["method"] == "POST"
    assert scrubbed["request"]["headers"]["User-Agent"] == "Safari"


def test_a_number_in_the_event_stays_a_number():
    """The scrubbing goes over the whole event: what is not a secret keeps its type."""
    event = {"extra": {"count": 3, "ok": True}, "status_code": 500}

    scrubbed = scrub_event(event)

    assert scrubbed["extra"] == {"count": 3, "ok": True}
    assert scrubbed["status_code"] == 500
