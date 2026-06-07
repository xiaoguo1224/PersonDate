from __future__ import annotations


def test_admin_users_manage_member_status_and_bindings(client, admin_token, member_token) -> None:
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member_headers = {"Authorization": f"Bearer {member_token}"}

    list_response = client.get("/api/admin/users", headers=admin_headers)
    assert list_response.status_code == 200
    usernames = [u["username"] for u in list_response.json()["data"]["items"]]
    assert "admin" in usernames
    assert "member1" in usernames

    member_list = client.get("/api/admin/users", headers=member_headers)
    assert member_list.status_code == 403
