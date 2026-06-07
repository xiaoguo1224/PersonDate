from __future__ import annotations


def test_wechat_login_session_and_unbind_flow(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    qr_response = client.get("/api/admin/wechat/status", headers=headers)
    assert qr_response.status_code == 200

    sessions_response = client.get("/api/admin/message-logs", headers=headers)
    assert sessions_response.status_code == 200


def test_wechat_message_logs_and_status(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    logs_response = client.get("/api/admin/message-logs", headers=headers)
    assert logs_response.status_code == 200


def test_admin_wechat_outbound_queue(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    queue_response = client.get("/api/admin/wechat/outbound-queue", headers=headers)
    assert queue_response.status_code == 200
