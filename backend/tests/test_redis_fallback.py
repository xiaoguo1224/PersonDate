from __future__ import annotations

import redis


def test_get_redis_degrades_on_redis_error(monkeypatch) -> None:
    from app.core import redis as redis_module

    class FakeClient:
        def ping(self) -> None:
            raise redis.ResponseError("unknown command HELLO")

    monkeypatch.setattr(redis_module, "_redis_client", None)
    monkeypatch.setattr(redis_module, "get_settings", lambda: type("S", (), {"redis_url": "redis://localhost:6379/0"})())
    monkeypatch.setattr(redis_module.redis, "from_url", lambda *args, **kwargs: FakeClient())

    client = redis_module.get_redis()

    assert client is None
