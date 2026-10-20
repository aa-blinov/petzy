"""The slots a day's doses are read against (web/dose_slots.py).

A schedule says «08:00, 20:00». The records that say which of those were handled carry a moment, and one
that does not carry a moment at all (an old record, a mark from another section) closes nothing: a slot is
closed only by a dose that says when it was given
"""

from datetime import datetime

from web.dose_slots import closed_slots, group_by_day, minutes_of_day, open_slots, slot_closers


def _at(hour, minute=0, day=2):
    return datetime(2026, 10, day, hour, minute)


def _made(hour, minute=0, **extra):
    return {"date_time": _at(hour, minute), **extra}


class TestTheTimeOfASlot:
    def test_a_time_written_as_two_numbers_is_read(self):
        assert minutes_of_day("08:30") == 510

    def test_a_time_that_is_not_written_as_two_numbers_is_no_time(self):
        """A slot time that cannot be read names no slot: the schedule of an old course may hold anything,
        and a time that is not a time must not be read as one."""
        assert minutes_of_day("830") is None
        assert minutes_of_day("08:30 вечера") is None

    def test_a_slot_time_that_is_not_a_time_closes_no_slot(self):
        """The slot that cannot be read is not closed by a dose: the dose closes the slot it can be read
        against, and the unreadable one stays open."""
        assert open_slots(["08:00", "не время"], [_made(8, 5)]) == ["не время"]

    def test_a_dose_without_a_time_closes_no_slot(self):
        """A record without a moment says nothing about the slots of the day."""
        assert open_slots(["08:00"], [{"medication_id": "m"}]) == ["08:00"]

    def test_a_dose_without_a_time_is_not_in_the_day_of_any_dose(self):
        """A record without a moment belongs to no day, so it is left out of the day's list."""
        assert group_by_day([{"medication_id": "m", "date_time": None}]) == {}

    def test_a_dose_with_a_slot_is_in_the_day_of_its_slot(self):
        assert group_by_day([{"medication_id": "m", "slot_date": "2026-10-02"}]) == {
            ("m", "2026-10-02"): [{"medication_id": "m", "slot_date": "2026-10-02"}]
        }


class TestTheSlotADoseCloses:
    def test_a_dose_naming_a_slot_the_schedule_no_longer_has_is_a_loose_dose(self):
        """The schedule lost the slot since: the dose closes the nearest slot that is still there."""
        assert closed_slots(["08:00"], [_made(8, 10, slot_date="2026-10-02", slot_time="07:00")]) == {"08:00"}

    def test_the_dose_that_closed_a_slot_is_named(self):
        closers = slot_closers(["08:00"], [_made(8, 0, medication_id="m")])
        assert closers["08:00"]["medication_id"] == "m"
