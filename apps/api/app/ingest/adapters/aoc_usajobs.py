"""Backward-compatible wrapper – delegates to the generic UsajobsAdapter."""

from app.ingest.adapters.usajobs import AOC_CONFIG, UsajobsAdapter


class AocUsajobsAdapter(UsajobsAdapter):
    """AOC adapter kept for backward compatibility with existing imports."""

    def __init__(self, api_key: str, user_agent_email: str = ""):
        super().__init__(AOC_CONFIG, api_key=api_key, user_agent_email=user_agent_email)
