from pydantic import BaseModel

from app.agent.llm_client import LLMClient


class DemoSchema(BaseModel):
    intent: str


def test_chat_json_parses_and_validates(monkeypatch) -> None:
    class _FakeResponse:
        class _Choice:
            class _Message:
                content = '{"intent":"create_event"}'

            message = _Message()

        choices = [_Choice()]

    class _FakeCompletions:
        def create(self, **kwargs):  # noqa: ANN003
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setattr("app.agent.llm_client.OpenAI", lambda **kwargs: _FakeClient())

    client = LLMClient(base_url="http://example.com", api_key="key", model="demo")
    result = client.chat_json(
        system_prompt="system",
        user_prompt="user",
        schema=DemoSchema,
    )

    assert result.intent == "create_event"


def test_anthropic_base_url_is_normalized(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class _FakeClient:
        chat = None

    def _fake_openai(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return _FakeClient()

    monkeypatch.setattr("app.agent.llm_client.OpenAI", _fake_openai)

    client = LLMClient(
        base_url="https://api.deepseek.com/anthropic",
        api_key="key",
        model="demo",
    )

    assert client.base_url == "https://api.deepseek.com"
    assert captured["base_url"] == "https://api.deepseek.com"
