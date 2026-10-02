import json
import logging
import time

from django.conf import settings
from google import genai
from google.genai import types

from .base import LLMProvider
from .schemas import DocumentClassification

logger = logging.getLogger(__name__)

_CLASSIFICATION_PROMPT = (
    "Read the following document and identify its type and the company it covers.\n\n"
)


class GeminiStructuredOutput(LLMProvider):

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    _MAX_RETRIES = 3

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        return "503" in str(exc) or "UNAVAILABLE" in str(exc)

    def _generate(self, user_message: str, system_prompt: str, schema: type):
        """Single Gemini call with schema-rejection fallback."""
        try:
            return self.client.models.generate_content(
                model=self.model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except Exception as e:
            if "too many states" in str(e).lower() or "INVALID_ARGUMENT" in str(e):
                logger.warning("Gemini rejected schema — falling back to prompt-embedded JSON")
                schema_json = json.dumps(schema.model_json_schema(), indent=2)
                return self.client.models.generate_content(
                    model=self.model,
                    contents=(
                        f"{user_message}\n\n"
                        f"Respond with a single JSON object matching this schema:\n{schema_json}"
                    ),
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                    ),
                )
            raise

    def run_agent(self, user_message: str, system_prompt: str, schema: type) -> dict:
        """
        Generic structured Gemini call used by all report agents.

        Retries up to _MAX_RETRIES times on transient 503 errors with
        exponential backoff (10 s, 20 s, 40 s) before giving up.
        """
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                response = self._generate(user_message, system_prompt, schema)
                break
            except Exception as e:
                if self._is_transient(e) and attempt < self._MAX_RETRIES:
                    delay = 10 * (2 ** attempt)
                    logger.warning(
                        "Gemini 503 — retrying in %ss (attempt %s/%s)",
                        delay, attempt + 1, self._MAX_RETRIES,
                    )
                    time.sleep(delay)
                else:
                    raise

        if not response.text:
            raise ValueError("Empty response from Gemini")

        return schema.model_validate_json(response.text).model_dump()

    def classify(self, md_content: str) -> dict:
        """Detect document_type and company_name from the first 8K chars of the document."""
        prompt = _CLASSIFICATION_PROMPT + md_content[:8000]
        return self.run_agent(prompt, "", DocumentClassification)
