"""The clock a value typed in a zone is judged against, and the wall clock of a zone, are that zone's, not the server's.

The server runs in UTC. At 00:30 on 16 October in Moscow it is still 21:30 on 15 October on the server, so a day counted
or a limit checked by the server's clock is the day before the person's. A request that names no zone is judged by the
server's clock, as it always was.
"""

from datetime import datetime, timezone

import pytest

from web.helpers import local_now, parse_date, parse_datetime, parse_event_datetime_safe

# 21:30 UTC on 15 October is 00:30 on 16 October in Moscow (UTC+3).
MIDNIGHT_IN_MOSCOW = datetime(2026, 10, 15, 21, 30, tzinfo=timezone.utc)
# 07:00 UTC on 16 October is 10:00 on 16 October in Moscow.
MORNING_IN_MOSCOW = datetime(2026, 10, 16, 7, 0, tzinfo=timezone.utc)


@pytest.mark.datetime
class TestLocalNow:
    def test_the_zones_wall_clock_comes_back_naive(self, frozen_clock):
        frozen_clock(MIDNIGHT_IN_MOSCOW)

        now = local_now("Europe/Moscow")

        assert now == datetime(2026, 10, 16, 0, 30)
        assert now.tzinfo is None

    def test_a_missing_or_unknown_zone_reads_utc(self, frozen_clock):
        frozen_clock(MIDNIGHT_IN_MOSCOW)

        assert local_now(None) == datetime(2026, 10, 15, 21, 30)
        assert local_now("Mars/Olympus") == datetime(2026, 10, 15, 21, 30)


@pytest.mark.datetime
class TestTheZoneJudgesWhatIsTyped:
    def test_a_day_ahead_is_judged_on_the_zones_clock(self, frozen_clock):
        # At 10:00 in Moscow, 09:00 tomorrow is inside one day. The server's clock (07:00) would refuse it.
        frozen_clock(MORNING_IN_MOSCOW)

        assert parse_datetime("2026-10-17", "09:00", tz="Europe/Moscow") == datetime(2026, 10, 17, 9, 0)

    def test_without_a_zone_the_servers_clock_judges_it_as_before(self, frozen_clock):
        frozen_clock(MORNING_IN_MOSCOW)

        with pytest.raises(ValueError, match="более чем на 1 день"):
            parse_datetime("2026-10-17", "09:00")

    def test_an_entry_without_a_time_is_stamped_on_the_zones_clock(self, frozen_clock):
        frozen_clock(MORNING_IN_MOSCOW)

        assert parse_event_datetime_safe("", "", tz="Europe/Moscow") == (datetime(2026, 10, 16, 10, 0), None)

    def test_a_birth_date_of_today_in_the_zone_is_not_in_the_future(self, frozen_clock):
        frozen_clock(MIDNIGHT_IN_MOSCOW)

        assert parse_date("2026-10-16", tz="Europe/Moscow") == datetime(2026, 10, 16)
        with pytest.raises(ValueError, match="в будущем"):
            parse_date("2026-10-17", tz="Europe/Moscow")
