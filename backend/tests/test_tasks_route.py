from __future__ import annotations

from app.services.task_service import TaskService


def test_list_tasks_returns_items(client, admin_token, owner, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    TaskService(db_session).create_task(
        user_id=owner.id,
        title="写论文",
        description=None,
        estimated_minutes=120,
        deadline=None,
        priority="high",
    )
    db_session.commit()

    response = client.get("/api/tasks", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"][0]["title"] == "写论文"
