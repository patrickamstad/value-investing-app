from ..llm.schemas import DocumentType
from .base import BaseReportAgent, ExecutionPattern
from .context_bundle import ContextBundle, DocumentContext
from .schemas import CompetitivePositionOutput


class CompetitivePositionAgent(BaseReportAgent):
    key           = "competitive_position"
    prompt_label  = "COMPETITIVE POSITION FINDINGS"
    pattern       = ExecutionPattern.SINGLE_CALL
    output_schema = CompetitivePositionOutput
    system_prompt = """
You are an expert in competitive analysis, trained in Michael Porter's Five Forces and
Warren Buffett's economic moat framework.

Assess:
- Whether a durable competitive advantage (moat) exists
- Moat type: network effects, switching costs, cost advantages, intangible assets, efficient scale
- Moat width: wide (20+ year durability), narrow (5-10 years), or none
- Industry structure: who captures value in this industry?
- Competitive threats: new entrants, substitutes, buyer/supplier power shifts

The strongest evidence for a real moat is ROIC sustained well above cost of capital for many
years. Be honest — most companies do not have wide moats.
""".strip()

    def select_documents(self, bundle: ContextBundle) -> list[DocumentContext]:
        return bundle.get_documents(types=[DocumentType.ANNUAL_REPORT], latest_n=1)

    def build_user_message(self, document: DocumentContext, bundle: ContextBundle) -> str:
        return f"""Assess the competitive position of {bundle.company_name} ({bundle.qfs_symbol}).

## RESEARCH DOCUMENTS
{bundle.raw_docs()}

## FINANCIAL METRICS
{self.select_financial_metrics(bundle) or "Not yet available — base your analysis on the documents."}

Provide a structured competitive position assessment.
"""
