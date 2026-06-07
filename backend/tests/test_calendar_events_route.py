from __future__ import annotations


def test_list_scheduled_items_can_filter_by_date(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    for payload in (
        {
            "title": "6日会议",
            "description": "过滤测试",
            "start_time": "2026-06-06T15:00:00+08:00",
            "end_time": "2026-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 10,
            "source": "manual",
        },
        {
            "title": "7日会议",
            "description": "过滤测试",
            "start_time": "2026-06-07T15:00:00+08:00",
            "end_time": "2026-06-07T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室B",
            "remind_before_minutes": 10,
            "source": "manual",
        },
    ):
        response = client.post("/api/scheduled-items", headers=headers, json=payload)
        assert response.status_code == 200

    response = client.get(
        "/api/scheduled-items?date=2026-06-06",
        headers=headers,
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["data"]["items"]] == ["6日会议"]


def test_past_scheduled_item_is_marked_completed(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.post(
        "/api/scheduled-items",
        headers=headers,
        json={
            "title": "历史会议",
            "description": "已结束",
            "start_time": "2025-06-06T15:00:00+08:00",
            "end_time": "2025-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 10,
            "source": "manual",
        },
    )
    assert response.status_code == 200

    list_response = client.get(
        "/api/scheduled-items?date=2025-06-06",
        headers=headers,
    )
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "历史会议"
