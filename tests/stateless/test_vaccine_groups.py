"""A change of brand is not a new vaccination: what a shot is against decides which entry replaces which."""

from datetime import date, timedelta

import pytest

from web.vaccines import GROUP_KEYS, GROUPS, PRODUCTS, effective_protects, infer_protects

TODAY = date.today()


def iso(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _post(client, token, pet, **fields):
    body = {"pet_id": str(pet["_id"]), "kind": "vaccination", "date": iso(-1), "title": "Нобивак DHPPi", **fields}
    response = client.post("/api/medical-records", json=body, headers=_auth(token))
    assert response.status_code == 201, response.get_json()
    return response.get_json()["id"]


def _by_id(client, token, pet):
    rows = client.get(f"/api/medical-records?pet_id={pet['_id']}", headers=_auth(token)).get_json()["records"]
    return {r["_id"]: r for r in rows}


class TestWhatAShotIsAgainst:
    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Нобивак DHPPi", "dhpp"),
            ("нобивак  dhppi", "dhpp"),
            ("Нобивак DHPPi (2025)", "dhpp"),
            ("Нобивак DHP", "dhpp"),  # the shorter name is not taken for the longer
            ("Эурикан DHPPi2-L", "dhpp"),
            ("Нобивак Rabies", "rabies"),
            ("Рабизин", "rabies"),
            ("Нобивак KC", "kennel"),
            ("Нобивак Tricat Trio", "fvrcp"),
            ("Леукоген", "felv"),
            ("Какая-то своя вакцина", None),
            ("", None),
        ],
    )
    def test_a_known_name_is_read_even_when_typed_by_hand(self, title, expected):
        assert infer_protects(title) == expected

    def test_a_kept_group_wins_over_the_name_and_only_a_vaccination_has_one(self):
        assert effective_protects({"kind": "vaccination", "title": "Нобивак DHPPi", "protects": "rabies"}) == "rabies"
        assert effective_protects({"kind": "vaccination", "title": "Нобивак DHPPi", "protects": "nonsense"}) == "dhpp"
        assert effective_protects({"kind": "parasite", "title": "Нобивак DHPPi", "protects": "rabies"}) is None

    def test_the_catalogue_is_consistent(self):
        assert {key for key, _, _, _ in GROUPS} == set(GROUP_KEYS)
        assert all(group in GROUP_KEYS for _, _, group in PRODUCTS)
        assert all(species for _, species, _ in PRODUCTS)
        names = {(name, species) for name, species, _ in PRODUCTS}
        assert len(names) == len(PRODUCTS)  # no product twice for the same species


@pytest.mark.health
class TestChangingTheBrand:
    def test_a_newer_shot_against_the_same_replaces_the_older_one_whatever_the_brand(
        self, client, regular_user_token, test_pet
    ):
        old = _post(client, regular_user_token, test_pet, date=iso(-400), next_due=iso(-35), title="Нобивак DHPPi")
        new = _post(client, regular_user_token, test_pet, date=iso(-2), next_due=iso(363), title="Эурикан DHPPi2")
        rows = _by_id(client, regular_user_token, test_pet)
        assert rows[old]["superseded"] is True and rows[old]["status"] == "none"
        assert rows[new]["superseded"] is False and rows[new]["status"] == "ok"
        assert rows[new]["protects"] == "dhpp" and "Комплексная для собак" in rows[new]["protects_label"]

    def test_a_shot_against_something_else_does_not(self, client, regular_user_token, test_pet):
        rabies = _post(client, regular_user_token, test_pet, date=iso(-400), next_due=iso(-35), title="Нобивак Rabies")
        _post(client, regular_user_token, test_pet, date=iso(-2), next_due=iso(363), title="Нобивак DHPPi")
        rows = _by_id(client, regular_user_token, test_pet)
        assert rows[rabies]["superseded"] is False and rows[rabies]["status"] == "overdue"

    def test_a_chosen_group_covers_a_name_the_catalogue_does_not_know(self, client, regular_user_token, test_pet):
        old = _post(
            client,
            regular_user_token,
            test_pet,
            date=iso(-400),
            next_due=iso(-35),
            title="Своя вакцина",
            protects="rabies",
        )
        new = _post(
            client,
            regular_user_token,
            test_pet,
            date=iso(-2),
            next_due=iso(363),
            title="Другая своя",
            protects="rabies",
        )
        rows = _by_id(client, regular_user_token, test_pet)
        assert rows[old]["superseded"] is True and rows[new]["superseded"] is False

    def test_older_entries_made_before_the_groups_are_read_by_their_name(
        self, client, mock_db, regular_user_token, test_pet
    ):
        # as the old data is: no group kept, only a name
        mock_db["medical_records"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "kind": "vaccination",
                "date": iso(-400),
                "title": "Нобивак DHPPi",
                "next_due": iso(-35),
                "document_ids": [],
            }
        )
        new = _post(client, regular_user_token, test_pet, date=iso(-2), next_due=iso(363), title="Эурикан DHPPi2")
        rows = list(_by_id(client, regular_user_token, test_pet).values())
        assert sorted(r["superseded"] for r in rows) == [False, True]
        assert [r for r in rows if r["_id"] == new][0]["superseded"] is False

    def test_two_names_nobody_knows_stay_two_vaccines(self, client, regular_user_token, test_pet):
        a = _post(client, regular_user_token, test_pet, date=iso(-400), next_due=iso(-35), title="Вакцина А")
        _post(client, regular_user_token, test_pet, date=iso(-2), next_due=iso(363), title="Вакцина Б")
        assert _by_id(client, regular_user_token, test_pet)[a]["superseded"] is False

    def test_the_same_name_still_replaces_with_no_group_known(self, client, regular_user_token, test_pet):
        a = _post(client, regular_user_token, test_pet, date=iso(-400), next_due=iso(-35), title="Вакцина А")
        _post(client, regular_user_token, test_pet, date=iso(-2), next_due=iso(363), title="вакцина  а")
        assert _by_id(client, regular_user_token, test_pet)[a]["superseded"] is True

    def test_an_unknown_group_is_refused_and_other_kinds_do_not_keep_one(self, client, regular_user_token, test_pet):
        refused = client.post(
            "/api/medical-records",
            json={
                "pet_id": str(test_pet["_id"]),
                "kind": "vaccination",
                "date": iso(-1),
                "title": "X",
                "protects": "nonsense",
            },
            headers=_auth(regular_user_token),
        )
        assert refused.status_code == 422
        visit = client.post(
            "/api/medical-records",
            json={
                "pet_id": str(test_pet["_id"]),
                "kind": "visit",
                "date": iso(-1),
                "title": "Осмотр",
                "protects": "rabies",
            },
            headers=_auth(regular_user_token),
        )
        assert visit.status_code == 201
        assert _by_id(client, regular_user_token, test_pet)[visit.get_json()["id"]]["protects"] is None

    def test_editing_keeps_and_changes_the_group(self, client, regular_user_token, test_pet):
        rid = _post(client, regular_user_token, test_pet, title="Своя вакцина", protects="rabies")
        assert _by_id(client, regular_user_token, test_pet)[rid]["protects"] == "rabies"
        body = {"date": iso(-1), "title": "Своя вакцина", "protects": "kennel"}
        assert (
            client.put(f"/api/medical-records/{rid}", json=body, headers=_auth(regular_user_token)).status_code == 200
        )
        assert _by_id(client, regular_user_token, test_pet)[rid]["protects"] == "kennel"


@pytest.mark.health
class TestChangingTheTreatment:
    def test_a_treatment_for_the_same_is_replaced_whatever_the_product(self, client, regular_user_token, test_pet):
        def post(title, date_days, due, target):
            body = {
                "pet_id": str(test_pet["_id"]),
                "kind": "parasite",
                "date": iso(date_days),
                "title": title,
                "next_due": iso(due),
                "target": target,
            }
            return client.post("/api/medical-records", json=body, headers=_auth(regular_user_token)).get_json()["id"]

        old = post("Бравекто", -120, -30, "fleas_ticks")
        worms = post("Дронтал Плюс", -100, -10, "worms")
        new = post("Нексгард", -2, 88, "fleas_ticks")
        rows = _by_id(client, regular_user_token, test_pet)
        assert rows[old]["superseded"] is True and rows[new]["superseded"] is False
        assert rows[worms]["superseded"] is False and rows[worms]["status"] == "overdue"


class TestTheCatalogue:
    def test_it_needs_a_sign_in_and_lists_groups_and_products(self, client, regular_user_token):
        assert client.get("/api/vaccines/catalog").status_code == 401
        body = client.get("/api/vaccines/catalog", headers=_auth(regular_user_token)).get_json()
        assert {g["key"] for g in body["groups"]} == set(GROUP_KEYS)
        assert any(
            p["name"] == "Нобивак DHPPi" and p["protects"] == "dhpp" and p["species"] == ["dog"]
            for p in body["products"]
        )
        assert len(body["products"]) >= 30
