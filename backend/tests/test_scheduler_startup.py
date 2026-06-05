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
        lambda: SimpleNamespace(reminder_scan_interval_seconds=15),
    )

    scheduler = scheduler_module.build_reminder_scheduler(
        session_factory=lambda: None,
        sender_provider=lambda: None,
    )

    assert scheduler is fake_scheduler
    assert len(fake_scheduler.jobs) == 1
    job = fake_scheduler.jobs[0]
    assert job["id"] == "reminder-scan"
    assert job["trigger"] == "interval"
    assert job["seconds"] == 15
    assert job["max_instances"] == 1
    assert job["coalesce"] is True


def test_create_app_starts_and_stops_scheduler(monkeypatch) -> None:
    from app import main as main_module

    fake_scheduler = FakeScheduler()

    monkeypatch.setattr(
        main_module,
        "build_reminder_scheduler",
        lambda session_factory=None, sender_provider=None: fake_scheduler,
    )

    app = main_module.create_app()

    with TestClient(app):
        assert app.state.reminder_scheduler is fake_scheduler
        assert fake_scheduler.started is True

    assert fake_scheduler.shutdown_called is True
