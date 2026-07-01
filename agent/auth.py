import os


def ensure_subscription_auth():
    """Drop ANTHROPIC_API_KEY so the Claude Agent SDK uses the subscription (CLAUDE_CODE_OAUTH_TOKEN),
    not an API key. Enforces the eval/scan auth invariant in code, not just docs."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
