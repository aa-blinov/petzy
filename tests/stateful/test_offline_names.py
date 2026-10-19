"""A record the device names itself, in every section a native client writes offline.

The feed of events already took a ``local_id``; courses, medical records, pets and the mark of an intake take it too.
The same name sent again is the record that is already there, the record can be changed or removed by its name before
the device has its id, and a name that belongs to another record or to a deleted one says so.
"""

from datetime import datetime, timezone

import pytest

TZ = "Asia/Almaty"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_pet(mock_db, regular_user):
    """Another pet of the same owner: a name given for one pet is not free for the other."""
    result = mock_db["pets"].insert_one(
        {
            "name": "Второй",
            "owner": regular_user["username"],
            "shared_with": [],
            "created_by": regular_user["username"],
            "created_at": datetime.now(timezone.utc),
        }
    )
    return result.inserted_id


@pytest.fixture
def stranger_token(mock_db):
    """A signed-in person with no access to the test pet."""
    from web.security import create_access_token

    mock_db["users"].insert_one(
        {
            "username": "stranger",
            "password_hash": "unused",
            "full_name": "Посторонний",
            "email": "",
            "created_at": datetime.now(timezone.utc),
            "created_by": "admin",
            "is_active": True,
        }
    )
    return create_access_token("stranger")


def _course(pet_id, **overrides):
    return {
        "pet_id": str(pet_id),
        "name": "Дронтал",
        "type": "Таблетка",
        "default_dose": 1,
        "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
        "inventory_enabled": True,
        "inventory_current": 10,
        **overrides,
    }


def _record(pet_id, **overrides):
    return {
        "pet_id": str(pet_id),
        "kind": "visit",
        "date": "2026-09-23",
        "title": "Осмотр",
        **overrides,
    }


class Section:
    """What differs between the sections: where to create, change and remove by name, and where the records live."""

    def __init__(self, name, collection, create_url, local_url, body, change, field):
        self.name, self.collection, self.create_url, self.local_url = name, collection, create_url, local_url
        self.body, self.change, self.field = body, change, field

    def __repr__(self):
        return self.name


SECTIONS = [
    Section(
        "medications",
        "medications",
        "/api/medications",
        "/api/medications/local/{}",
        lambda pet, **kw: _course(pet, **kw),
        {"name": "Новое имя"},
        "name",
    ),
    Section(
        "medical_records",
        "medical_records",
        "/api/medical-records",
        "/api/medical-records/local/{}",
        lambda pet, **kw: _record(pet, **kw),
        {"date": "2026-09-23", "title": "Новое имя"},
        "title",
    ),
]


@pytest.fixture(params=SECTIONS, ids=repr)
def section(request):
    return request.param


@pytest.mark.health_records
class TestACourseAndARecordKeepTheirName:
    def test_the_name_is_kept_and_answered(self, client, mock_db, regular_user_token, test_pet, section):
        response = client.post(
            section.create_url, json=section.body(test_pet["_id"], local_id="a1"), headers=_auth(regular_user_token)
        )

        assert response.status_code == 201
        assert response.get_json()["local_id"] == "a1"
        [stored] = list(mock_db[section.collection].find({"local_id": "a1"}))
        assert str(stored["_id"]) == response.get_json()["id"]

    def test_without_a_name_the_record_keeps_no_field(self, client, mock_db, regular_user_token, test_pet, section):
        client.post(section.create_url, json=section.body(test_pet["_id"]), headers=_auth(regular_user_token))

        [stored] = list(mock_db[section.collection].find({}))
        assert "local_id" not in stored

    def test_the_same_request_sent_again_is_the_record_already_there(
        self, client, mock_db, regular_user_token, test_pet, section
    ):
        body = section.body(test_pet["_id"], local_id="a1")
        first = client.post(section.create_url, json=body, headers=_auth(regular_user_token))
        again = client.post(section.create_url, json=body, headers=_auth(regular_user_token))

        assert (first.status_code, again.status_code) == (201, 200)
        assert again.get_json()["id"] == first.get_json()["id"]
        assert mock_db[section.collection].count_documents({}) == 1

    def test_a_name_that_belongs_to_another_pets_record_is_taken(
        self, client, mock_db, regular_user_token, test_pet, second_pet, section
    ):
        client.post(
            section.create_url, json=section.body(test_pet["_id"], local_id="a1"), headers=_auth(regular_user_token)
        )

        response = client.post(
            section.create_url, json=section.body(second_pet, local_id="a1"), headers=_auth(regular_user_token)
        )

        assert (response.status_code, response.get_json()["code"]) == (409, "local_id_taken")
        assert mock_db[section.collection].count_documents({}) == 1

    def test_a_blank_name_names_nothing(self, client, regular_user_token, test_pet, section):
        response = client.post(
            section.create_url, json=section.body(test_pet["_id"], local_id="  "), headers=_auth(regular_user_token)
        )

        assert response.status_code == 422

    def test_a_name_is_at_most_64_characters(self, client, regular_user_token, test_pet, section):
        response = client.post(
            section.create_url, json=section.body(test_pet["_id"], local_id="x" * 65), headers=_auth(regular_user_token)
        )

        assert response.status_code == 422

    def test_the_record_can_be_changed_by_its_name(self, client, mock_db, regular_user_token, test_pet, section):
        client.post(
            section.create_url, json=section.body(test_pet["_id"], local_id="a1"), headers=_auth(regular_user_token)
        )

        response = client.put(section.local_url.format("a1"), json=section.change, headers=_auth(regular_user_token))

        assert response.status_code == 200
        [stored] = list(mock_db[section.collection].find({}))
        assert stored[section.field] == "Новое имя"
        assert stored["local_id"] == "a1"

    def test_the_record_can_be_removed_by_its_name(self, client, mock_db, regular_user_token, test_pet, section):
        client.post(
            section.create_url, json=section.body(test_pet["_id"], local_id="a1"), headers=_auth(regular_user_token)
        )

        response = client.delete(section.local_url.format("a1"), headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert mock_db[section.collection].count_documents({}) == 0

    def test_an_unknown_name_and_somebody_elses_record_answer_alike(
        self, client, regular_user_token, stranger_token, test_pet, section
    ):
        client.post(
            section.create_url, json=section.body(test_pet["_id"], local_id="a1"), headers=_auth(regular_user_token)
        )

        unknown = client.put(section.local_url.format("zzz"), json=section.change, headers=_auth(regular_user_token))
        foreign = client.put(section.local_url.format("a1"), json=section.change, headers=_auth(stranger_token))
        foreign_delete = client.delete(section.local_url.format("a1"), headers=_auth(stranger_token))

        for answer in (unknown, foreign, foreign_delete):
            assert (answer.status_code, answer.get_json()["code"]) == (404, "record_not_found")

    def test_a_record_deleted_is_told_so_by_its_name_and_not_made_again(
        self, client, mock_db, regular_user_token, test_pet, section
    ):
        body = section.body(test_pet["_id"], local_id="a1")
        client.post(section.create_url, json=body, headers=_auth(regular_user_token))
        client.delete(section.local_url.format("a1"), headers=_auth(regular_user_token))

        edited = client.put(section.local_url.format("a1"), json=section.change, headers=_auth(regular_user_token))
        repeated = client.post(section.create_url, json=body, headers=_auth(regular_user_token))
        removed = client.delete(section.local_url.format("a1"), headers=_auth(regular_user_token))

        assert (edited.status_code, edited.get_json()["code"]) == (409, "record_deleted")
        assert (repeated.status_code, repeated.get_json()["code"]) == (409, "record_deleted")
        assert (removed.status_code, removed.get_json()["code"]) == (404, "record_not_found")
        assert mock_db[section.collection].count_documents({}) == 0

    def test_a_record_deleted_by_its_id_is_told_so_to_an_edit_by_id(
        self, client, mock_db, regular_user_token, test_pet, stranger_token, section
    ):
        created = client.post(
            section.create_url, json=section.body(test_pet["_id"], local_id="a1"), headers=_auth(regular_user_token)
        ).get_json()
        url = section.create_url + "/" + created["id"]
        client.delete(url, headers=_auth(regular_user_token))

        mine = client.put(url, json=section.change, headers=_auth(regular_user_token))
        theirs = client.put(url, json=section.change, headers=_auth(stranger_token))

        assert (mine.status_code, mine.get_json()["code"]) == (409, "record_deleted")
        # Who could not see the record is not told that it ever was.
        assert (theirs.status_code, theirs.get_json()["code"]) == (404, "record_not_found")

    def test_the_name_comes_back_in_the_reading(self, client, regular_user_token, test_pet, section):
        created = client.post(
            section.create_url, json=section.body(test_pet["_id"], local_id="a1"), headers=_auth(regular_user_token)
        ).get_json()

        listed = client.get(f"{section.create_url}?pet_id={test_pet['_id']}", headers=_auth(regular_user_token))
        one = client.get(f"{section.create_url}/{created['id']}", headers=_auth(regular_user_token))

        items = listed.get_json()[{"medications": "medications", "medical_records": "records"}[section.name]]
        assert [item["local_id"] for item in items] == ["a1"]
        assert next(iter(one.get_json().values()))["local_id"] == "a1"


@pytest.mark.health_records
class TestAPetKeepsItsName:
    def test_the_name_is_kept_and_answered(self, client, mock_db, regular_user_token):
        response = client.post(
            "/api/pets", json={"name": "Мурзик", "local_id": "p1"}, headers=_auth(regular_user_token)
        )

        assert response.status_code == 201
        assert response.get_json()["pet"]["local_id"] == "p1"
        assert mock_db["pets"].count_documents({"local_id": "p1"}) == 1

    def test_the_same_request_sent_again_is_the_pet_already_there(self, client, mock_db, regular_user_token):
        body = {"name": "Мурзик", "local_id": "p1"}
        first = client.post("/api/pets", json=body, headers=_auth(regular_user_token))
        again = client.post("/api/pets", json=body, headers=_auth(regular_user_token))

        assert (first.status_code, again.status_code) == (201, 200)
        assert again.get_json()["pet"]["_id"] == first.get_json()["pet"]["_id"]
        assert mock_db["pets"].count_documents({}) == 1

    def test_a_multipart_request_sent_again_stores_no_second_photo(
        self, client, mock_db, regular_user_token, s3_storage
    ):
        import io

        from PIL import Image

        def send():
            buffer = io.BytesIO()
            Image.new("RGB", (8, 8), "red").save(buffer, "PNG")
            buffer.seek(0)
            return client.post(
                "/api/pets",
                data={"name": "Мурзик", "local_id": "p1", "photo_file": (buffer, "cat.png")},
                headers=_auth(regular_user_token),
                content_type="multipart/form-data",
            )

        first, again = send(), send()

        assert (first.status_code, again.status_code) == (201, 200)
        assert again.get_json()["pet"]["_id"] == first.get_json()["pet"]["_id"]
        assert again.get_json()["pet"]["local_id"] == "p1"

    def test_a_name_that_belongs_to_somebody_elses_pet_is_taken(
        self, client, mock_db, regular_user_token, stranger_token
    ):
        client.post("/api/pets", json={"name": "Мурзик", "local_id": "p1"}, headers=_auth(regular_user_token))

        response = client.post("/api/pets", json={"name": "Барсик", "local_id": "p1"}, headers=_auth(stranger_token))

        assert (response.status_code, response.get_json()["code"]) == (409, "local_id_taken")
        assert mock_db["pets"].count_documents({}) == 1

    def test_the_pet_can_be_changed_and_removed_by_its_name(self, client, mock_db, regular_user_token):
        client.post("/api/pets", json={"name": "Мурзик", "local_id": "p1"}, headers=_auth(regular_user_token))

        changed = client.put("/api/pets/local/p1", json={"name": "Барсик"}, headers=_auth(regular_user_token))
        [stored] = list(mock_db["pets"].find({}))
        removed = client.delete("/api/pets/local/p1", headers=_auth(regular_user_token))

        assert changed.status_code == 200
        assert stored["name"] == "Барсик" and stored["local_id"] == "p1"
        assert removed.status_code == 200
        assert mock_db["pets"].count_documents({}) == 0

    def test_only_the_owner_changes_a_pet_by_its_name(self, client, mock_db, regular_user_token, stranger_token):
        client.post("/api/pets", json={"name": "Мурзик", "local_id": "p1"}, headers=_auth(regular_user_token))
        mock_db["pets"].update_one({"local_id": "p1"}, {"$set": {"shared_with": ["stranger"]}})

        member = client.put("/api/pets/local/p1", json={"name": "Чужой"}, headers=_auth(stranger_token))
        member_delete = client.delete("/api/pets/local/p1", headers=_auth(stranger_token))

        assert member.status_code == member_delete.status_code == 403
        assert mock_db["pets"].find_one({"local_id": "p1"})["name"] == "Мурзик"

    def test_an_unknown_name_and_somebody_elses_pet_answer_alike(self, client, regular_user_token, stranger_token):
        client.post("/api/pets", json={"name": "Мурзик", "local_id": "p1"}, headers=_auth(regular_user_token))

        for token, name in ((regular_user_token, "zzz"), (stranger_token, "p1")):
            answer = client.put(f"/api/pets/local/{name}", json={"name": "X"}, headers=_auth(token))
            assert (answer.status_code, answer.get_json()["code"]) == (404, "record_not_found")

    def test_a_pet_deleted_is_told_so_and_not_made_again(self, client, mock_db, regular_user_token):
        body = {"name": "Мурзик", "local_id": "p1"}
        created = client.post("/api/pets", json=body, headers=_auth(regular_user_token)).get_json()["pet"]
        client.delete(f"/api/pets/{created['_id']}", headers=_auth(regular_user_token))

        by_name = client.put("/api/pets/local/p1", json={"name": "X"}, headers=_auth(regular_user_token))
        by_id = client.put(f"/api/pets/{created['_id']}", json={"name": "X"}, headers=_auth(regular_user_token))
        repeated = client.post("/api/pets", json=body, headers=_auth(regular_user_token))

        for answer in (by_name, by_id, repeated):
            assert (answer.status_code, answer.get_json()["code"]) == (409, "record_deleted")
        assert mock_db["pets"].count_documents({}) == 0

    def test_the_name_comes_back_in_the_reading(self, client, regular_user_token):
        created = client.post(
            "/api/pets", json={"name": "Мурзик", "local_id": "p1"}, headers=_auth(regular_user_token)
        ).get_json()["pet"]

        listed = client.get("/api/pets", headers=_auth(regular_user_token)).get_json()["pets"]
        one = client.get(f"/api/pets/{created['_id']}", headers=_auth(regular_user_token)).get_json()["pet"]

        assert [pet["local_id"] for pet in listed] == ["p1"]
        assert one["local_id"] == "p1"


@pytest.mark.health_records
class TestAnIntakeMarkKeepsItsName:
    """A mark sent from a queue can arrive twice: the second is the first, and not «already marked»."""

    @pytest.fixture
    def course(self, client, regular_user_token, test_pet):
        response = client.post(
            "/api/medications", json=_course(test_pet["_id"], local_id="m1"), headers=_auth(regular_user_token)
        )
        return response.get_json()["id"]

    @staticmethod
    def _mark(client, token, course, **overrides):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        body = {
            "date": today,
            "time": "08:05",
            "tz": "UTC",
            "slot_date": today,
            "slot_time": "08:00",
            **overrides,
        }
        return client.post(f"/api/medications/{course}/log", json=body, headers=_auth(token))

    def test_a_mark_sent_again_is_the_mark_already_made_and_takes_the_stock_once(
        self, client, mock_db, regular_user_token, course
    ):
        first = self._mark(client, regular_user_token, course, local_id="d1")
        again = self._mark(client, regular_user_token, course, local_id="d1")

        assert (first.status_code, again.status_code) == (201, 200)
        assert again.get_json()["id"] == first.get_json()["id"]
        assert again.get_json()["local_id"] == "d1"
        assert mock_db["medication_intakes"].count_documents({}) == 1
        assert mock_db["medications"].find_one({})["inventory_current"] == 9

    def test_the_repeat_says_what_the_first_answer_said_about_the_stock(
        self, client, mock_db, regular_user_token, course
    ):
        mock_db["medications"].update_one({}, {"$set": {"inventory_current": 1}})

        first = self._mark(client, regular_user_token, course, local_id="d1")
        again = self._mark(client, regular_user_token, course, local_id="d1")

        assert first.get_json()["ran_out"] is True
        assert again.get_json()["ran_out"] is True

    def test_without_a_name_the_same_slot_is_still_a_duplicate(self, client, mock_db, regular_user_token, course):
        self._mark(client, regular_user_token, course)
        again = self._mark(client, regular_user_token, course)

        assert (again.status_code, again.get_json()["code"]) == (409, "duplicate_intake")
        assert mock_db["medication_intakes"].count_documents({}) == 1

    def test_another_mark_of_the_slot_with_another_name_is_still_a_duplicate(
        self, client, mock_db, regular_user_token, course
    ):
        self._mark(client, regular_user_token, course, local_id="d1")
        other = self._mark(client, regular_user_token, course, local_id="d2")

        assert (other.status_code, other.get_json()["code"]) == (409, "duplicate_intake")

    def test_a_name_held_by_somebody_elses_mark_is_taken(self, client, mock_db, regular_user_token, test_pet, course):
        from web.security import create_access_token

        mock_db["users"].insert_one(
            {
                "username": "partner",
                "password_hash": "unused",
                "full_name": "Партнёр",
                "email": "",
                "created_at": datetime.now(timezone.utc),
                "created_by": "admin",
                "is_active": True,
            }
        )
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["partner"]}})
        self._mark(client, regular_user_token, course, local_id="d1")

        theirs = self._mark(client, create_access_token("partner"), course, local_id="d1")

        assert (theirs.status_code, theirs.get_json()["code"]) == (409, "local_id_taken")
        assert mock_db["medication_intakes"].count_documents({}) == 1

    def test_a_name_held_by_a_mark_of_another_course_is_taken(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        other = client.post(
            "/api/medications", json=_course(test_pet["_id"], name="Другой"), headers=_auth(regular_user_token)
        ).get_json()["id"]
        self._mark(client, regular_user_token, course, local_id="d1")

        response = self._mark(client, regular_user_token, other, local_id="d1")

        assert (response.status_code, response.get_json()["code"]) == (409, "local_id_taken")

    def test_the_name_comes_back_in_the_list_of_intakes(self, client, regular_user_token, test_pet, course):
        self._mark(client, regular_user_token, course, local_id="d1")

        listed = client.get(f"/api/medications/intakes?pet_id={test_pet['_id']}", headers=_auth(regular_user_token))

        intakes = listed.get_json()["intakes"]
        assert [i["local_id"] for i in intakes] == ["d1"]
        assert "ran_out" not in intakes[0]
