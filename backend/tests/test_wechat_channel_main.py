from __future__ import annotations

from types import SimpleNamespace


def test_wechat_channel_main_enters_idle_mode_without_base_url(monkeypatch) -> None:
    from app import wechat_channel_main as wechat_channel_main_module

    fake_app = SimpleNamespace(state=SimpleNamespace())
    scheduler_called = False
    sleep_calls: list[float] = []

    monkeypatch.setattr(wechat_channel_main_module, "create_app", lambda: fake_app)
    monkeypatch.setattr(wechat_channel_main_module, "build_wechat_channel_client", lambda: None)

    def fake_build_wechat_channel_scheduler(**kwargs):  # noqa: ANN001
        nonlocal scheduler_called
        scheduler_called = True
        raise AssertionError("scheduler should not start without WECHAT_CHANNEL_BASE_URL")

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        raise KeyboardInterrupt

    monkeypatch.setattr(
        wechat_channel_main_module,
        "build_wechat_channel_scheduler",
        fake_build_wechat_channel_scheduler,
    )

    wechat_channel_main_module.run(sleep_fn=fake_sleep)

    assert scheduler_called is False
    assert sleep_calls == [1]
    assert getattr(fake_app.state, "wechat_sender", None) is None
    assert getattr(fake_app.state, "wechat_updates_client", None) is None
