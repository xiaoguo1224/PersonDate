from __future__ import annotations

from fastapi.testclient import TestClient


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


def test_wechat_channel_app_starts_poll_scheduler_when_client_exists(monkeypatch) -> None:
    from app import wechat_channel_app as wechat_channel_app_module

    class FakeScheduler:
        def __init__(self) -> None:
            self.started = False
            self.shutdown_called = False

        def start(self) -> None:
            self.started = True

        def shutdown(self, wait: bool = True) -> None:
            self.shutdown_called = True

    fake_scheduler = FakeScheduler()
    fake_client = object()
    app_module = __import__("app.wechat_channel_main", fromlist=["dummy"])

    def fake_attach(app):  # noqa: ANN001
        app.state.wechat_updates_client = fake_client

    monkeypatch.setattr(app_module, "attach_wechat_channel_client", fake_attach)
    monkeypatch.setattr(
        app_module,
        "build_wechat_channel_scheduler",
        lambda updates_client_provider=None, session_factory=None: fake_scheduler,
    )
    monkeypatch.setattr(app_module, "close_wechat_channel_client", lambda app: None)

    app = wechat_channel_app_module.create_wechat_channel_app()

    with TestClient(app):
        assert app.state.wechat_channel_scheduler is fake_scheduler
        assert fake_scheduler.started is True

    assert fake_scheduler.shutdown_called is True


def test_wechat_channel_app_stays_idle_without_client(monkeypatch) -> None:
    from app import wechat_channel_app as wechat_channel_app_module

    app_module = __import__("app.wechat_channel_main", fromlist=["dummy"])
    called: list[str] = []

    def fake_attach(app):  # noqa: ANN001
        app.state.wechat_updates_client = None
        called.append("attach")

    monkeypatch.setattr(app_module, "attach_wechat_channel_client", fake_attach)
    monkeypatch.setattr(
        app_module,
        "build_wechat_channel_scheduler",
        lambda updates_client_provider=None, session_factory=None: (_ for _ in ()).throw(AssertionError("scheduler should not start")),  # noqa: E501
    )
    monkeypatch.setattr(app_module, "close_wechat_channel_client", lambda app: None)

    app = wechat_channel_app_module.create_wechat_channel_app()

    with TestClient(app):
        assert app.state.wechat_channel_scheduler is None

    assert called == ["attach"]
