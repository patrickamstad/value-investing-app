from enum import Enum
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    ANNUAL_REPORT         = "annual_report"
    QUARTERLY_REPORT      = "quarterly_report"
    EARNINGS_CALL         = "earnings_call"
    INVESTOR_PRESENTATION = "investor_presentation"
    ANALYST_REPORT        = "analyst_report"
    NEWS_ARTICLE          = "news_article"
    OTHER                 = "other"


class DocumentClassification(BaseModel):
    """Cheap first-pass call: detect document type and company name."""
    document_type: DocumentType = Field(
        description="Type of document inferred from content."
    )
    company_name: str = Field(
        description="Full legal name of the company the document is about."
    )
