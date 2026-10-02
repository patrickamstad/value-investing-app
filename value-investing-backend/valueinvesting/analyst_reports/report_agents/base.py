from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel

from .context_bundle import ContextBundle, DocumentContext

logger = logging.getLogger(__name__)


class ExecutionPattern(str, Enum):
    SINGLE_CALL            = "single_call"
    MAP_REDUCE             = "map_reduce"
    MULTI_SOURCE_SYNTHESIS = "multi_source_synthesis"


class BaseReportAgent(ABC):
    """
    Base class for all analysis agents in the report pipeline.

    Each agent declares its execution pattern and implements the corresponding
    message-builder method(s). BaseReportAgent.run() routes automatically.

    Patterns:
      SINGLE_CALL            — one LLM call, one document
      MAP_REDUCE             — parallel per-document map calls, then one reduce call
      MULTI_SOURCE_SYNTHESIS — one LLM call with all selected documents simultaneously

    To add a new agent:
      1. Subclass BaseReportAgent in a new file
      2. Declare: key, prompt_label, system_prompt, output_schema, pattern
      3. Declare reduce_schema if using MAP_REDUCE
      4. Implement select_documents()
      5. Implement the message builder(s) for your pattern
      6. Register the class in registry.py
    """

    key: ClassVar[str]
    prompt_label: ClassVar[str]
    system_prompt: ClassVar[str]

    output_schema: ClassVar[type[BaseModel]]
    """
    Primary structured output schema.
    For MAP_REDUCE: this is the per-document map-phase schema.
    For all other patterns: this is the final output schema.
    """

    reduce_schema: ClassVar[type[BaseModel] | None] = None
    """
    Final output schema for the MAP_REDUCE reduce phase.
    Must be set when pattern == MAP_REDUCE. May differ from output_schema.
    """

    pattern: ClassVar[ExecutionPattern]

    # ── Document selection ────────────────────────────────────────────────────

    @abstractmethod
    def select_documents(self, bundle: ContextBundle) -> list[DocumentContext]:
        """Return the subset of documents this agent should process."""

    def select_financial_metrics(self, bundle: ContextBundle) -> str:
        """Return financial metrics for inclusion in prompts. Override to restrict to a subset."""
        return bundle.financial_metrics

    # ── Message builders — implement the one(s) matching your pattern ─────────

    def build_user_message(self, document: DocumentContext, bundle: ContextBundle) -> str:
        """
        SINGLE_CALL: called once with the first selected document.
        MAP_REDUCE:  called once per document during the map phase.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement build_user_message() "
            f"for pattern {self.pattern}"
        )

    def build_reduce_message(
        self,
        map_outputs: list[BaseModel],
        bundle: ContextBundle,
    ) -> str:
        """
        MAP_REDUCE reduce phase only.
        Receives typed Pydantic objects from the map phase in document order.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement build_reduce_message() "
            f"for MAP_REDUCE pattern"
        )

    def build_synthesis_message(
        self,
        documents: list[DocumentContext],
        bundle: ContextBundle,
    ) -> str:
        """MULTI_SOURCE_SYNTHESIS only. Receives all selected documents simultaneously."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement build_synthesis_message() "
            f"for MULTI_SOURCE_SYNTHESIS pattern"
        )

    # ── Execution routing ─────────────────────────────────────────────────────

    def run(self, bundle: ContextBundle, provider) -> dict:
        if self.pattern == ExecutionPattern.SINGLE_CALL:
            return self._run_single_call(bundle, provider)
        elif self.pattern == ExecutionPattern.MAP_REDUCE:
            return self._run_map_reduce(bundle, provider)
        elif self.pattern == ExecutionPattern.MULTI_SOURCE_SYNTHESIS:
            return self._run_multi_source_synthesis(bundle, provider)
        else:
            raise ValueError(f"Unknown execution pattern: {self.pattern!r}")

    def _run_single_call(self, bundle: ContextBundle, provider) -> dict:
        docs = self.select_documents(bundle)
        if not docs:
            logger.warning("%s: no documents selected, running with empty context", self.key)
        document = docs[0] if docs else DocumentContext(
            file_name="none", document_type="other", raw_markdown="No documents available."
        )
        return provider.run_agent(
            user_message=self.build_user_message(document, bundle),
            system_prompt=self.system_prompt,
            schema=self.output_schema,
        )

    def _run_map_reduce(self, bundle: ContextBundle, provider) -> dict:
        if self.reduce_schema is None:
            raise ValueError(
                f"{self.__class__.__name__} uses MAP_REDUCE but reduce_schema is not defined"
            )

        docs = self.select_documents(bundle)
        if not docs:
            logger.warning("%s: no documents for map phase, skipping to reduce", self.key)
            return self._reduce([], bundle, provider)

        map_results: list[tuple[int, BaseModel]] = []

        def _map_one(idx_doc: tuple[int, DocumentContext]):
            idx, doc = idx_doc
            raw = provider.run_agent(
                user_message=self.build_user_message(doc, bundle),
                system_prompt=self.system_prompt,
                schema=self.output_schema,
            )
            return idx, self.output_schema.model_validate(raw)

        max_workers = min(len(docs), 4)  # cap to avoid hitting rate limits
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_map_one, (i, doc)): i
                for i, doc in enumerate(docs)
            }
            for future in as_completed(futures):
                map_results.append(future.result())

        # Restore original document order — as_completed() yields in completion order
        map_results.sort(key=lambda t: t[0])
        ordered_outputs = [obj for _, obj in map_results]

        # Expose map outputs so callers (e.g. the Celery task) can persist them.
        # Each entry carries the source document filename so the array is self-describing.
        self._map_outputs: list[dict] = [
            {"document": doc.file_name, "output": obj.model_dump()}
            for doc, obj in zip(docs, ordered_outputs)
        ]

        return self._reduce(ordered_outputs, bundle, provider)

    def _reduce(
        self,
        map_outputs: list[BaseModel],
        bundle: ContextBundle,
        provider,
    ) -> dict:
        return provider.run_agent(
            user_message=self.build_reduce_message(map_outputs, bundle),
            system_prompt=self.system_prompt,
            schema=self.reduce_schema,
        )

    def _run_multi_source_synthesis(self, bundle: ContextBundle, provider) -> dict:
        docs = self.select_documents(bundle)
        return provider.run_agent(
            user_message=self.build_synthesis_message(docs, bundle),
            system_prompt=self.system_prompt,
            schema=self.output_schema,
        )
