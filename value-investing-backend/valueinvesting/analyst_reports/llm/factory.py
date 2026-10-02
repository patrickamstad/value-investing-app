from .base import LLMProvider
from .gemini import GeminiStructuredOutput

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "gemini": GeminiStructuredOutput,
}


def get_provider(name: str) -> LLMProvider:
    provider_class = _PROVIDERS.get(name)
    if provider_class is None:
        raise ValueError(f"Unknown LLM provider: '{name}'. Available: {list(_PROVIDERS)}")
    return provider_class()
