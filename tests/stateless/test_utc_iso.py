"""Every timestamp the API writes is UTC to the second with a Z: the form a default ISO 8601 decoder reads."""

from datetime import datetime, timedelta, timezone

from web.helpers import utc_iso


def test_a_moment_without_a_zone_is_utc_to_the_second():
    assert utc_iso(datetime(2026, 10, 18, 8, 12, 33, 987654)) == "2026-10-18T08:12:33Z"


def test_an_aware_moment_is_converted_to_utc_to_the_second():
    moment = datetime(2026, 10, 18, 13, 12, 33, 500000, tzinfo=timezone(timedelta(hours=5)))

    assert utc_iso(moment) == "2026-10-18T08:12:33Z"
