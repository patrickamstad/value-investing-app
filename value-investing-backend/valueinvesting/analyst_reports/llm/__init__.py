from django.conf import settings

from .factory import get_provider


def classify(md_content: str) -> dict:
    """Detect document_type and company_name from raw markdown. Returns a dict."""
    provider_name = getattr(settings, "LLM_PROVIDER", "gemini")
    return get_provider(provider_name).classify(md_content)
