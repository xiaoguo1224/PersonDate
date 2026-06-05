from __future__ import annotations


def test_wechat_channel_main_starts_protocol_app(monkeypatch) -> None:
    from app import wechat_channel_main as wechat_channel_main_module

    called: dict[str, object] = {}

    def fake_serve(*args, **kwargs):  # noqa: ANN001
        called["args"] = args
        called["kwargs"] = kwargs

    wechat_channel_main_module.run(serve_fn=fake_serve)

    assert called["args"] == ("app.wechat_channel_app:app",)
    assert called["kwargs"]["host"] == "0.0.0.0"
    assert called["kwargs"]["port"] == 18789
    assert called["kwargs"]["log_level"] == "info"
