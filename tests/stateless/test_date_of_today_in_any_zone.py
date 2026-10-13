"""A date of today is valid for a person whose calendar is a day ahead of the server's (east of UTC).

The server runs in UTC and the app sends the person's own date. Before this, a birth date of today was refused
for the hours after the person's local midnight. One day of slack keeps today valid; two days ahead is still refused.
"""

from datetime import datetime, timedelta

import pytest

from web.schemas import PetCreate


def test_a_birth_date_of_today_on_the_servers_calendar_is_accepted():
    today = datetime.now().strftime("%Y-%m-%d")
    assert PetCreate(name="Рекс", birth_date=today).birth_date == today


def test_a_birth_date_a_day_ahead_of_the_server_is_accepted():
    ahead = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert PetCreate(name="Рекс", birth_date=ahead).birth_date == ahead


def test_a_birth_date_two_days_ahead_is_refused():
    too_far = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    with pytest.raises(ValueError, match="Дата не может быть в будущем"):
        PetCreate(name="Рекс", birth_date=too_far)
