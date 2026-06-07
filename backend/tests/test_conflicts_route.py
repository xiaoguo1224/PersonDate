from __future__ import annotations

from datetime import UTC, datetime, timedelta

_FUTURE_DATE = (datetime.now(UTC) + timedelta(days=30)).strftime("%Y-%m-%d")


def _create_event(client, headers, title: str, start: str, end: str, location: str = "会议室") -> dict:
    resp = client.post(
        "/api/scheduled-items",
        headers=headers,
        json={
            "title": title,
            "description": "测试冲突",
            "start_time": start,
            "end_time": end,
            "timezone": "Asia/Shanghai",
            "location": location,
            "remind_before_minutes": 10,
            "source": "manual",
        },
    )
    assert resp.status_code == 200
    return resp.json()["data"]


def test_detect_conflicts_returns_persisted_ids(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    _create_event(client, headers, "会议A", f"{_FUTURE_DATE}T15:00:00+08:00", f"{_FUTURE_DATE}T16:00:00+08:00", "会议室A")
    _create_event(client, headers, "会议B", f"{_FUTURE_DATE}T15:30:00+08:00", f"{_FUTURE_DATE}T16:30:00+08:00", "会议室B")

    response = client.post("/api/conflicts/detect", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    items = body["data"]["items"]
    assert len(items) == 1
    assert items[0]

    list_response = client.get("/api/conflicts?status=open", headers=headers)
    assert list_response.status_code == 200
    listed = list_response.json()["data"]["items"]
    assert len(listed) == 1
    assert listed[0]["id"]
    assert listed[0]["title"] == "安排冲突：会议A 与 会议B"


def test_detect_conflicts_deduplicates_repeated_pairs(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    _create_event(client, headers, "会议A", f"{_FUTURE_DATE}T15:00:00+08:00", f"{_FUTURE_DATE}T16:00:00+08:00", "会议室A")
    _create_event(client, headers, "会议B", f"{_FUTURE_DATE}T15:30:00+08:00", f"{_FUTURE_DATE}T16:30:00+08:00", "会议室B")

    first_detect = client.post("/api/conflicts/detect", headers=headers)
    second_detect = client.post("/api/conflicts/detect", headers=headers)
    list_response = client.get("/api/conflicts?status=open", headers=headers)

    assert first_detect.status_code == 200
    assert second_detect.status_code == 200
    assert len(first_detect.json()["data"]["items"]) == 1
    assert len(second_detect.json()["data"]["items"]) == 0
    assert len(list_response.json()["data"]["items"]) == 1


def test_deleting_event_resolves_related_conflicts(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    event_a = _create_event(client, headers, "开会", f"{_FUTURE_DATE}T15:00:00+08:00", f"{_FUTURE_DATE}T16:00:00+08:00", "会议室A")
    event_id = event_a["id"]
    _create_event(client, headers, "API自动化测试 日程 B", f"{_FUTURE_DATE}T15:30:00+08:00", f"{_FUTURE_DATE}T16:30:00+08:00", "会议室B")

    client.post("/api/conflicts/detect", headers=headers)

    before_delete = client.get("/api/conflicts?status=open", headers=headers)
    assert before_delete.status_code == 200
    assert len(before_delete.json()["data"]["items"]) == 1

    delete_response = client.delete(f"/api/scheduled-items/{event_id}", headers=headers)
    assert delete_response.status_code == 200

    after_delete = client.get("/api/conflicts?status=open", headers=headers)
    resolved_response = client.get("/api/conflicts?status=resolved", headers=headers)

    assert after_delete.status_code == 200
    assert resolved_response.status_code == 200
    assert after_delete.json()["data"]["items"] == []
    assert len(resolved_response.json()["data"]["items"]) == 1


def test_list_conflicts_auto_resolves_finished_pairs(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    _create_event(client, headers, "已结束会议A", "2025-06-06T15:00:00+08:00", "2025-06-06T16:00:00+08:00", "会议室A")
    _create_event(client, headers, "已结束会议B", "2025-06-06T15:30:00+08:00", "2025-06-06T16:30:00+08:00", "会议室B")

    detect_response = client.post("/api/conflicts/detect", headers=headers)
    assert detect_response.status_code == 200

    open_response = client.get("/api/conflicts?status=open", headers=headers)
    resolved_response = client.get("/api/conflicts?status=resolved", headers=headers)

    assert open_response.status_code == 200
    assert resolved_response.status_code == 200
    assert open_response.json()["data"]["items"] == []
    resolved_items = resolved_response.json()["data"]["items"]
    assert len(resolved_items) == 1
    assert resolved_items[0]["status"] == "resolved"
