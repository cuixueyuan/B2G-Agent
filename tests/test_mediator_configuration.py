from b2g_agent.collaboration.mediator import B2GMediator


def test_placeholder_api_key_uses_offline_fallback(monkeypatch) -> None:
    monkeypatch.setenv("B2G_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "your_openai_api_key_here")

    mediator = B2GMediator()

    assert mediator.configured is False
    assert mediator.last_backend == "local-fallback"
