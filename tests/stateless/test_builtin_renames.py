"""A builtin type still carrying an old default name gets the new one; a chosen name stays."""

from web.builtin_event_types import BUILTIN_TYPE_ORDER, reorder_default_tiles, seed_builtin_event_types


def _feeding(label, field_label):
    return {
        "key": "feeding",
        "label": label,
        "is_builtin": True,
        "fields": [{"name": "food_weight", "label": field_label, "type": "number"}],
    }


def test_old_defaults_are_renamed(mock_db):
    mock_db.event_types.delete_many({"key": "feeding"})
    mock_db.event_types.insert_one(_feeding("Дневная порция", "Вес корма"))
    seed_builtin_event_types(mock_db)
    feeding = mock_db.event_types.find_one({"key": "feeding"})
    assert feeding["label"] == "Кормление"
    assert feeding["fields"][0]["label"] == "Вес корма (г)"


def test_a_chosen_name_is_kept(mock_db):
    mock_db.event_types.delete_many({"key": "feeding"})
    mock_db.event_types.insert_one(_feeding("Еда Барсика", "Сколько съел"))
    seed_builtin_event_types(mock_db)
    feeding = mock_db.event_types.find_one({"key": "feeding"})
    assert feeding["label"] == "Еда Барсика"
    assert feeding["fields"][0]["label"] == "Сколько съел"


def test_types_come_in_frequency_order_then_custom_by_name(client, mock_db, auth_headers):
    for key, label in (("walk", "Прогулка"), ("bath", "Купание")):
        mock_db.event_types.insert_one(
            {
                "key": key,
                "label": label,
                "icon": "paw",
                "color": "blue",
                "fields": [],
                "is_builtin": False,
                "created_by": "admin",
            }
        )
    keys = [t["key"] for t in client.get("/api/event-types", headers=auth_headers).get_json()["event_types"]]
    builtins = [k for k in keys if k not in ("walk", "bath")]
    assert builtins[:4] == ["feeding", "weight", "defecation", "litter"]
    assert keys[-2:] == ["bath", "walk"]


def test_pets_on_the_old_alphabetical_order_move_to_the_new_one(mock_db):
    old = ["weight", "defecation", "feeding", "eye_drops", "asthma", "litter", "ear_cleaning", "tooth_brushing"]
    mine = ["asthma", "feeding", "weight"]
    mock_db.pets.insert_one({"name": "A", "tiles_settings": {"order": old, "visible": {}}})
    mock_db.pets.insert_one({"name": "B", "tiles_settings": {"order": mine, "visible": {}}})
    assert reorder_default_tiles(mock_db) == 1
    assert mock_db.pets.find_one({"name": "A"})["tiles_settings"]["order"] == BUILTIN_TYPE_ORDER
    # Reordered by hand: kept.
    assert mock_db.pets.find_one({"name": "B"})["tiles_settings"]["order"] == mine
