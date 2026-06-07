from __future__ import annotations


def test_scheduled_item_crud(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = client.post(
        "/api/scheduled-items",
        headers=headers,
        json={
            "title": "写论文",
            "start_time": "2026-06-06T17:00:00+08:00",
            "end_time": "2026-06-06T19:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "source": "manual",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]
    item_id = created["id"]
    assert created["title"] == "写论文"

    list_response = client.get(
        "/api/scheduled-items?date=2026-06-06",
        headers=headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["id"] == item_id

    update_response = client.patch(
        f"/api/scheduled-items/{item_id}",
        headers=headers,
        json={
            "title": "写论文初稿",
            "start_time": "2026-06-06T18:00:00+08:00",
            "end_time": "2026-06-06T20:00:00+08:00",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["title"] == "写论文初稿"

    complete_response = client.patch(
        f"/api/scheduled-items/{item_id}/complete",
        headers=headers,
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["data"]["status"] == "completed"

    delete_response = client.delete(
        f"/api/scheduled-items/{item_id}",
        headers=headers,
    )
    assert delete_response.status_code == 200

    get_response = client.get(
        f"/api/scheduled-items/{item_id}",
        headers=headers,
    )
    assert get_response.status_code == 404


def test_scheduled_item_generate_and_confirm(client, admin_token, owner, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models import TaskItem
    from app.models.enums import TaskStatus

    task = TaskItem(
        user_id=owner.id,
        title="写论文",
        estimated_minutes=120,
        status=TaskStatus.PENDING.value,
    )
    db_session.add(task)
    db_session.commit()

    gen_response = client.post(
        "/api/scheduled-items/generate/2026-06-07",
        headers=headers,
        json={},
    )
    assert gen_response.status_code == 200
    items = gen_response.json()["data"]["items"]
    assert len(items) >= 1
    assert all(item["status"] == "draft" for item in items)

    confirm_response = client.post(
        "/api/scheduled-items/confirm",
        headers=headers,
        json={"plan_date": "2026-06-07"},
    )
    assert confirm_response.status_code == 200
