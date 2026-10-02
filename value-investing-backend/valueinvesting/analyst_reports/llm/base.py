from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Blueprint for LLM providers used in the analyst report pipeline."""

    @abstractmethod
    def classify(self, md_content: str) -> dict:
        """
        Detect document_type and company_name from raw markdown.
        Returns a dict with at least a 'document_type' key.
        Only called when the user has not explicitly set the document type.
        """

    @abstractmethod
    def run_agent(self, user_message: str, system_prompt: str, schema: type) -> dict:
        """
        Generic structured LLM call used by all report agents.
        Takes a fully assembled user message, a system prompt, and a Pydantic
        schema for constrained decoding. Returns a dict matching that schema.
        """
