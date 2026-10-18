"""Инструменты MCP: какие запросы уходят в Petzy, что отказывается до запроса и что возвращается модели."""

import asyncio
import json

import pytest

from petzy_mcp import tools
from petzy_mcp.client import BAD_RESPONSE, PetzyClient, PetzyError
from tests.mcp.fake_petzy import BASE_URL, PET_ID, TOKEN, FakePetzy

RECORD_ID = "65f0c0ffee0000000000abcd"


def _call(petzy, tool, **kwargs):
    if getattr(tool, "__name__", "") == "add_event":
        kwargs.setdefault("tz", "Asia/Almaty")  # the zone is required now: the tests add the usual one

    async def go():
        async with PetzyClient(BASE_URL, TOKEN, petzy.transport) as api:
            return await tool(api, **kwargs)

    return asyncio.run(go())


def _refused(petzy, tool, message, **kwargs):
    with pytest.raises(PetzyError) as refused:
        _call(petzy, tool, **kwargs)
    assert refused.value.message == message
    assert petzy.requests == [], "to refuse the arguments, no request may reach Petzy"


# list_pets ------------------------------------------------------------------------------------------------------------


def test_list_pets_asks_for_pets_and_keeps_three_fields():
    petzy = FakePetzy()
    petzy.answer(
        "GET",
        "/api/pets",
        body={
            "pets": [
                {
                    "_id": PET_ID,
                    "name": "Рекс",
                    "species": "dog",
                    "owner": "demo",
                    "health_notes": "не любит фен",
                    "shared_with": [],
                }
            ]
        },
    )

    result = _call(petzy, tools.list_pets)

    assert [(r.method, r.url.path) for r in petzy.requests] == [("GET", "/api/pets")]
    assert result == {"pets": [{"id": PET_ID, "name": "Рекс", "species": "dog"}]}


def test_list_pets_refuses_an_answer_without_a_list():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", body={"pets": None})

    with pytest.raises(PetzyError) as refused:
        _call(petzy, tools.list_pets)

    assert refused.value.message == BAD_RESPONSE


# list_event_types -----------------------------------------------------------------------------------------------------


def test_list_event_types_keeps_what_a_record_needs_and_drops_the_rest():
    petzy = FakePetzy()
    petzy.answer(
        "GET",
        "/api/event-types",
        body={
            "event_types": [
                {
                    "key": "weight",
                    "label": "Вес",
                    "icon": "scale",
                    "color": "blue",
                    "is_builtin": True,
                    "category": "health",
                    "created_by": None,
                    "chart": {"kind": "value", "value_field": "weight"},
                    "fields": [
                        {
                            "name": "weight",
                            "label": "Вес (кг)",
                            "type": "number",
                            "required": True,
                            "min": 0.01,
                            "max": 100,
                            "step": 0.01,
                            "options": None,
                            "deviation_threshold": 0.15,
                        },
                        {
                            "name": "food",
                            "label": "Корм",
                            "type": "select",
                            "required": False,
                            "options": [{"value": "dry", "text": "Сухой", "extra": 1}],
                        },
                    ],
                }
            ]
        },
    )

    result = _call(petzy, tools.list_event_types)

    assert [(r.method, r.url.path) for r in petzy.requests] == [("GET", "/api/event-types")]
    assert result == {
        "event_types": [
            {
                "key": "weight",
                "label": "Вес",
                "fields": [
                    {
                        "name": "weight",
                        "label": "Вес (кг)",
                        "type": "number",
                        "required": True,
                        "min": 0.01,
                        "max": 100,
                        "step": 0.01,
                    },
                    {
                        "name": "food",
                        "label": "Корм",
                        "type": "select",
                        "required": False,
                        "options": [{"value": "dry", "text": "Сухой"}],
                    },
                ],
            }
        ]
    }


# add_event ------------------------------------------------------------------------------------------------------------


def _saved(petzy):
    petzy.answer(
        "POST",
        "/api/events",
        status=201,
        body={"success": True, "message": "Запись «Вес» добавлена", "id": RECORD_ID},
    )


def test_add_event_posts_one_record_and_answers_with_what_was_sent():
    petzy = FakePetzy()
    _saved(petzy)

    result = _call(
        petzy,
        tools.add_event,
        pet_id=PET_ID,
        type="weight",
        date="2026-10-16",
        time="09:30",
        fields={"weight": 12.4},
        comment="после прогулки",
    )

    [sent] = petzy.requests
    assert (sent.method, sent.url.path) == ("POST", "/api/events")
    assert sent.url.query == b"", "the pet goes in the body: EventCreate requires it there"
    assert json.loads(sent.content) == {
        "pet_id": PET_ID,
        "type": "weight",
        "date": "2026-10-16",
        "time": "09:30",
        "fields": {"weight": 12.4},
        "comment": "после прогулки",
        "tz": "Asia/Almaty",
    }
    assert result == {
        "id": RECORD_ID,
        "type": "weight",
        "date": "2026-10-16",
        "time": "09:30",
        "fields": {"weight": 12.4},
        "comment": "после прогулки",
    }


def test_the_timezone_is_sent_with_every_record():
    """A clock with no zone is not saved, so the tool sends the zone the person named, every time."""
    petzy = FakePetzy()
    _saved(petzy)

    _call(
        petzy,
        tools.add_event,
        pet_id=PET_ID,
        type="weight",
        date="2026-10-16",
        time="09:30",
        fields={},
        tz="Europe/Moscow",
    )

    [sent] = petzy.requests
    assert json.loads(sent.content)["tz"] == "Europe/Moscow"


@pytest.mark.parametrize("zone", ["", "Europe/Moscow " * 10])
def test_a_zone_of_no_shape_is_refused_before_any_request(zone):
    petzy = FakePetzy()

    with pytest.raises(PetzyError):
        _call(petzy, tools.add_event, pet_id=PET_ID, type="weight", date="2026-10-16", time="09:30", fields={}, tz=zone)

    assert petzy.requests == []


@pytest.mark.parametrize("date", ["2026-02-30", "16.10.2026", "2026-10-1", "2026-10-16T09:30", "", None])
def test_add_event_refuses_a_date_that_is_not_a_real_day_before_asking_petzy(date):
    _refused(
        FakePetzy(),
        tools.add_event,
        tools.BAD_DATE,
        pet_id=PET_ID,
        type="weight",
        date=date,
        time="09:30",
        fields={},
    )


@pytest.mark.parametrize("time", ["7:05", "25:00", "09:60", "09:30:00", "", None])
def test_add_event_refuses_a_time_that_is_not_hh_mm_before_asking_petzy(time):
    _refused(
        FakePetzy(),
        tools.add_event,
        tools.BAD_TIME,
        pet_id=PET_ID,
        type="weight",
        date="2026-10-16",
        time=time,
        fields={},
    )


@pytest.mark.parametrize(
    "pet_id",
    ["../events", "507f1f77bcf86cd79943901", "507f1f77bcf86cd7994390111", "zzzzzzzzzzzzzzzzzzzzzzzz", "", None],
)
def test_add_event_refuses_a_pet_id_that_is_not_an_object_id(pet_id):
    _refused(
        FakePetzy(),
        tools.add_event,
        tools.BAD_PET_ID,
        pet_id=pet_id,
        type="weight",
        date="2026-10-16",
        time="09:30",
        fields={},
    )


@pytest.mark.parametrize("fields", [None, [], "weight=12"])
def test_add_event_refuses_fields_that_are_not_a_mapping(fields):
    _refused(
        FakePetzy(),
        tools.add_event,
        tools.BAD_FIELDS,
        pet_id=PET_ID,
        type="weight",
        date="2026-10-16",
        time="09:30",
        fields=fields,
    )


@pytest.mark.parametrize("type_key", ["", "   ", "x" * 61, None])
def test_add_event_refuses_an_empty_or_too_long_type(type_key):
    _refused(
        FakePetzy(),
        tools.add_event,
        tools.BAD_TYPE,
        pet_id=PET_ID,
        type=type_key,
        date="2026-10-16",
        time="09:30",
        fields={},
    )


def test_add_event_refuses_a_comment_longer_than_500_characters_and_takes_500():
    _refused(
        FakePetzy(),
        tools.add_event,
        tools.BAD_COMMENT,
        pet_id=PET_ID,
        type="weight",
        date="2026-10-16",
        time="09:30",
        fields={},
        comment="я" * 501,
    )

    petzy = FakePetzy()
    _saved(petzy)
    _call(
        petzy,
        tools.add_event,
        pet_id=PET_ID,
        type="weight",
        date="2026-10-16",
        time="09:30",
        fields={},
        comment="я" * 500,
    )
    assert len(petzy.requests) == 1


def test_add_event_refuses_a_timezone_longer_than_64_characters():
    _refused(
        FakePetzy(),
        tools.add_event,
        tools.BAD_TZ,
        pet_id=PET_ID,
        type="weight",
        date="2026-10-16",
        time="09:30",
        fields={},
        tz="z" * 65,
    )


def test_an_answer_without_an_id_is_not_reported_as_saved():
    petzy = FakePetzy()
    petzy.answer("POST", "/api/events", status=201, body={"success": True, "message": "Запись добавлена"})

    with pytest.raises(PetzyError) as refused:
        _call(petzy, tools.add_event, pet_id=PET_ID, type="weight", date="2026-10-16", time="09:30", fields={})

    assert refused.value.message == tools.UNCONFIRMED


# get_history ----------------------------------------------------------------------------------------------------------


def test_get_history_asks_for_the_newest_records_of_one_pet_and_twenty_by_default():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/history/timeline", body={"items": [], "page": 1, "page_size": 20, "total": 0})

    _call(petzy, tools.get_history, pet_id=PET_ID)

    [sent] = petzy.requests
    assert sent.url.path == "/api/history/timeline"
    assert sent.url.params.get("pet_id") == PET_ID
    assert sent.url.params.get("page") == "1"
    assert sent.url.params.get("page_size") == "20"
    assert "type" not in sent.url.params


@pytest.mark.parametrize("limit", [1, 100])
def test_get_history_accepts_both_ends_of_the_range(limit):
    petzy = FakePetzy()
    petzy.answer("GET", "/api/history/timeline", body={"items": [], "total": 0})

    _call(petzy, tools.get_history, pet_id=PET_ID, limit=limit)

    assert petzy.requests[0].url.params.get("page_size") == str(limit)


@pytest.mark.parametrize("limit", [0, -1, 101, 1000, True, "20", 2.5, None])
def test_get_history_refuses_a_limit_outside_one_to_a_hundred(limit):
    _refused(FakePetzy(), tools.get_history, tools.BAD_LIMIT, pet_id=PET_ID, limit=limit)


def test_history_items_keep_what_a_record_says_and_drop_who_wrote_it():
    petzy = FakePetzy()
    petzy.answer(
        "GET",
        "/api/history/timeline",
        body={
            "items": [
                {
                    "_id": "a1",
                    "record_type": "weight",
                    "pet_id": PET_ID,
                    "date_time": "2026-10-16 09:30",
                    "username": "owner@example",
                    "created_at": "2026-10-16 09:31",
                    "tz": "Europe/Moscow",
                    "fields": {"weight": 12.4},
                    "comment": "",
                },
                {
                    "_id": "b2",
                    "record_type": "medications",
                    "pet_id": PET_ID,
                    "date_time": "2026-10-16 08:00",
                    "username": "owner@example",
                    "medication_id": "m1",
                    "medication_name": "Метацам",
                    "dose_taken": 1,
                    "dose_unit": "1 мл",
                    "skipped": False,
                    "inventory_deducted": 1,
                    "comment": "с кормом",
                },
                {
                    "_id": "c3",
                    "record_type": "medications",
                    "date_time": "2026-10-15 20:00",
                    "medication_name": "Метацам",
                    "dose_taken": 1,
                    "dose_unit": None,
                    "skipped": True,
                },
            ],
            "page": 1,
            "page_size": 20,
            "total": 3,
        },
    )

    result = _call(petzy, tools.get_history, pet_id=PET_ID)

    assert result == {
        "items": [
            {"id": "a1", "record_type": "weight", "date_time": "2026-10-16 09:30", "fields": {"weight": 12.4}},
            {
                "id": "b2",
                "record_type": "medications",
                "date_time": "2026-10-16 08:00",
                "comment": "с кормом",
                "medication_name": "Метацам",
                "dose_taken": 1,
                "dose_unit": "1 мл",
            },
            {
                "id": "c3",
                "record_type": "medications",
                "date_time": "2026-10-15 20:00",
                "medication_name": "Метацам",
                "dose_taken": 1,
                "skipped": True,
            },
        ],
        "total": 3,
    }


# get_medical_card -----------------------------------------------------------------------------------------------------


def test_the_medical_card_drops_empty_values_and_keeps_zeros_and_empty_lists():
    petzy = FakePetzy()
    petzy.answer(
        "GET",
        f"/api/pets/{PET_ID}/medical-card",
        body={
            "card": {
                "pet": {"name": "Рекс", "breed": None, "health_notes": "", "is_neutered": False},
                "records": {"vaccination": [], "parasite": [{"title": "Гельминты", "note": None}]},
                "weight": {"latest": 0, "series": []},
                "can_edit": True,
                "generated_at": "2026-10-16",
            }
        },
    )

    result = _call(petzy, tools.get_medical_card, pet_id=PET_ID)

    assert [(r.method, r.url.path) for r in petzy.requests] == [("GET", f"/api/pets/{PET_ID}/medical-card")]
    assert result == {
        "card": {
            "pet": {"name": "Рекс", "is_neutered": False},
            "records": {"vaccination": [], "parasite": [{"title": "Гельминты"}]},
            "weight": {"latest": 0, "series": []},
            "generated_at": "2026-10-16",
        },
        "truncated": False,
    }


def test_a_card_longer_than_the_limit_keeps_whole_sections_and_names_the_rest():
    long_text = "Наблюдение. " * 1000  # about 12 000 characters
    petzy = FakePetzy()
    petzy.answer(
        "GET",
        f"/api/pets/{PET_ID}/medical-card",
        body={
            "card": {
                "pet": {"name": "Рекс"},
                "visit_prep": {"notes": long_text},
                "documents": [{"title": long_text}, {"title": long_text}],
                "records": {"vaccination": []},
            }
        },
    )

    result = _call(petzy, tools.get_medical_card, pet_id=PET_ID)

    assert result["truncated"] is True
    assert "ответ обрезан" in result["note"]
    assert "documents" in result["note"]
    assert list(result["card"]) == ["pet", "visit_prep"]
    assert len(json.dumps(result["card"], ensure_ascii=False, separators=(",", ":"))) <= tools.MEDICAL_CARD_MAX_CHARS


@pytest.mark.parametrize("pet_id", ["../records", "507f1f77bcf86cd79943901", "", None])
def test_the_medical_card_refuses_a_pet_id_that_is_not_an_object_id(pet_id):
    _refused(FakePetzy(), tools.get_medical_card, tools.BAD_PET_ID, pet_id=pet_id)
