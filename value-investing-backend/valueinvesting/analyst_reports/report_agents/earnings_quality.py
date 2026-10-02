import json

from ..llm.schemas import DocumentType
from .base import BaseReportAgent, ExecutionPattern
from .context_bundle import ContextBundle, DocumentContext
from .schemas import EarningsQualityOutput, EarningsQualityPerYearOutput


class EarningsQualityAgent(BaseReportAgent):
    key           = "earnings_quality"
    prompt_label  = "EARNINGS QUALITY FINDINGS"
    pattern       = ExecutionPattern.MAP_REDUCE
    output_schema = EarningsQualityPerYearOutput  # map phase: per-document
    reduce_schema = EarningsQualityOutput         # reduce phase: cross-period verdict
    system_prompt = """
You are an expert in earnings quality analysis, trained in the frameworks of Doron Nissim
and Richard Sloan.

Focus on:
- Accruals analysis: operating accruals vs. cash-based earnings (high accruals = red flag)
- Revenue recognition: aggressive vs. conservative accounting policies
- Working capital signals: unusual receivables or inventory build relative to revenue
- Pension obligations, off-balance-sheet items, and their earnings impact
- Earnings persistence: recurring vs. transitory components
- Cash conversion: does net income translate reliably to free cash flow?

Be sceptical. Report findings factually; do not over-interpret missing data.
""".strip()

    def select_documents(self, bundle: ContextBundle) -> list[DocumentContext]:
        return bundle.get_documents(types=[
            DocumentType.ANNUAL_REPORT,
            DocumentType.QUARTERLY_REPORT,
        ])

    def build_user_message(self, document: DocumentContext, bundle: ContextBundle) -> str:
        return f"""Assess earnings quality for {bundle.company_name} ({bundle.qfs_symbol}) \
for the period covered by this document.

## DOCUMENT: {document.file_name} ({document.document_type})
{document.raw_markdown}

## FINANCIAL METRICS
{self.select_financial_metrics(bundle) or "Not yet available — base your analysis on the document."}

Provide a per-period earnings quality assessment. Identify the fiscal year from the document \
and include it in the fiscal_year field.
"""

    def build_reduce_message(self, map_outputs, bundle: ContextBundle) -> str:
        per_year_json = json.dumps([o.model_dump() for o in map_outputs], indent=2)
        return f"""You have completed per-period earnings quality analysis for \
{bundle.company_name} ({bundle.qfs_symbol}).

## PER-PERIOD FINDINGS
{per_year_json}

Synthesise these findings into a cross-period verdict:
- Is earnings quality improving, stable, or deteriorating over time?
- Are any concerns persistent across periods (structural) vs. one-off?
- What is the overall earnings quality rating?

Provide the integrated earnings quality assessment.
"""
