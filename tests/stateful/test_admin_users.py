"""Границы доступа в админ-панели: администратор не отключает сам себя.

Деактивация обрывает все сессии человека, а экран, на котором это можно вернуть обратно, после неё
недоступен. Для встроенной учётной записи это правило было, для любой другой учётной записи администратора,
которая сможет появиться вместе с новыми правами, его не было: PUT /api/users/<свой логин> с
«is_active: false» отключал того, кто этот запрос и послал.
"""

import pytest


@pytest.mark.admin
class TestAdminCannotDeactivateSelf:
    def test_updating_own_account_to_inactive_is_refused(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put("/api/users/admin", json={"is_active": False}, headers=headers)
        assert response.status_code == 422
        assert response.get_json()["error"] == "Нельзя деактивировать самого себя"

    def test_admin_can_still_deactivate_someone_else(self, client, admin_token, regular_user):
        response = client.put(
            f"/api/users/{regular_user['username']}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.get_json()["success"] is True


@pytest.mark.admin
class TestAdminListTellsAnUnconfirmedAddress:
    """Список людей показывает «Не подтверждена» у неподтверждённого адреса.

    Метка в админке рисуется по email_verified === false, то есть поле должно
    доезжать до клиента вместе со списком, а не обрезаться по дороге.
    """

    def test_list_carries_email_verified(self, client, admin_token, mock_db, regular_user):
        mock_db["users"].update_one({"username": regular_user["username"]}, {"$set": {"email_verified": False}})
        response = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        row = next(u for u in response.get_json()["users"] if u["username"] == regular_user["username"])
        assert row.get("email_verified") is False, response.get_json()

    def test_a_user_without_an_address_is_not_called_unconfirmed(self, client, admin_token, regular_user):
        response = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
        row = next(u for u in response.get_json()["users"] if u["username"] == regular_user["username"])
        assert row.get("email_verified") is None, response.get_json()
