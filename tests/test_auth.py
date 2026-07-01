import os
from agent.auth import ensure_subscription_auth


def test_pops_anthropic_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-be-removed")
    ensure_subscription_auth()
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_noop_when_absent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ensure_subscription_auth()  # must not raise
    assert "ANTHROPIC_API_KEY" not in os.environ
