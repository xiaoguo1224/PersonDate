from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient


class FakeScheduler:
    def __init__(self) -> None:
        self.started = False
        self.shutdown_called = False
        self.jobs: list[dict[str, object]] = []

    def add_job(self, func, trigger: str, **kwargs):  # noqa: ANN001
        self.jobs.append({"func": func, "trigger": trigger, **kwargs})
        return SimpleNamespace(id=kwargs.get("id"))

    def start(self) -> None:
        self.started = True

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_called = True


def test_build_reminder_scheduler_registers_interval_job(monkeypatch) -> None:
    from app.core import scheduler as scheduler_module

    fake_scheduler = FakeScheduler()
    monkeypatch.setattr(scheduler_module, "BackgroundScheduler", lambda **kwargs: fake_scheduler)
    monkeypatch.setattr(
        scheduler_module,
        "get_settings",
        lambda: SimpleNamespace(
            reminder_scan_interval_seconds=15,
            wechat_poll_interval_seconds=7,
        ),
    )

    scheduler = scheduler_module.build_reminder_scheduler(
        session_factory=lambda: None,
        sender_provider=lambda: None,
        updates_client_provider=lambda: None,
    )

    assert scheduler is fake_scheduler
    assert len(fake_scheduler.jobs) == 2
    reminder_job = next(job for job in fake_scheduler.jobs if job["id"] == "reminder-scan")
    wechat_job = next(job for job in fake_scheduler.jobs if job["id"] == "wechat-poll-scan")
    assert reminder_job["trigger"] == "interval"
    assert reminder_job["seconds"] == 15
    assert reminder_job["max_instances"] == 1
    assert reminder_job["coalesce"] is True
    assert wechat_job["trigger"] == "interval"
    assert wechat_job["seconds"] == 7
    assert wechat_job["max_instances"] == 1
    assert wechat_job["coalesce"] is True


def test_create_app_starts_and_stops_scheduler(monkeypatch) -> None:
    from app import main as main_module

    fake_scheduler = FakeScheduler()

    monkeypatch.setattr(
        main_module,
        "build_reminder_scheduler",
        lambda session_factory=None, sender_provider=None, updates_client_provider=None: fake_scheduler,  # noqa: E501
    )

    app = main_module.create_app()

    with TestClient(app):
        assert app.state.reminder_scheduler is fake_scheduler
        assert fake_scheduler.started is True

    assert fake_scheduler.shutdown_called is True


def test_run_wechat_poll_scan_dispatches_active_accounts(monkeypatch) -> None:
    from app.core import scheduler as scheduler_module

    class FakePoller:
        def __init__(self, db, updates_client, adapter=None) -> None:  # noqa: ANN001
            self.db = db
            self.updates_client = updates_client
            self.adapter = adapter
            self.calls: list[str] = []

        def poll_active_accounts_once(self):
            assert self.updates_client is fake_updates_client
            self.calls.append("poll")
            return 1

    class FakeSession:
        def close(self) -> None:
            self.closed = True

    fake_session = FakeSession()
    fake_updates_client = object()

    monkeypatch.setattr(scheduler_module, "WechatChannelPoller", FakePoller)

    processed = scheduler_module.run_wechat_poll_scan(
        session_factory=lambda: fake_session,
        updates_client_provider=lambda: fake_updates_client,
    )

    assert processed == 1
    assert getattr(fake_session, "closed", False) is True
