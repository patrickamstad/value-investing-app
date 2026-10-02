from __future__ import annotations

from dataclasses import dataclass, field

from ..llm.schemas import DocumentType


@dataclass
class DocumentContext:
    file_name: str
    document_type: DocumentType | str   # str fallback for "other" / unknown values
    raw_markdown: str                   # from ocr_s3_key


@dataclass
class ContextBundle:
    qfs_symbol: str
    company_name: str
    documents: list[DocumentContext] = field(default_factory=list)
    financial_metrics: str = ""   # TODO: from quickfs_dj
    valuation_data: str = ""      # TODO: from valuation_history
    insider_data: str = ""        # TODO: from quickfs_dj
    shareholder_data: str = ""    # TODO: from quickfs_dj

    def get_documents(
        self,
        types: list[DocumentType] | None = None,
        latest_n: int | None = None,
    ) -> list[DocumentContext]:
        """Return documents filtered by DocumentType. Pass latest_n to cap the result."""
        docs = self.documents if types is None else [
            d for d in self.documents if d.document_type in types
        ]
        if latest_n is not None:
            docs = docs[:latest_n]
        return docs

    def raw_docs(self, types: list[DocumentType] | None = None) -> str:
        docs = self.get_documents(types=types)
        if not docs:
            return "No relevant documents available."
        blocks = [
            f"### [{i + 1}] {d.file_name} ({d.document_type})\n\n{d.raw_markdown}"
            for i, d in enumerate(docs)
        ]
        return "\n\n---\n\n".join(blocks)
