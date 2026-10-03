import os

from app.llm import ProviderName


def personal_allowed(provider: ProviderName) -> bool:
    return provider == "groq" and all(
        os.environ.get(flag) == "true"
        for flag in (
            "LLM_ENABLED",
            "LLM_FREE_TIER_CONFIRMED",
            "GROQ_PERSONAL_DATA_ENABLED",
            "GROQ_ZDR_CONFIRMED",
        )
    )
