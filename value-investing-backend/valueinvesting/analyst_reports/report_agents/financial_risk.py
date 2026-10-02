import json

from ..llm.schemas import DocumentType
from .base import BaseReportAgent, ExecutionPattern
from .context_bundle import ContextBundle, DocumentContext
from .schemas import FinancialRiskOutput, FinancialRiskPerYearOutput


class FinancialRiskAgent(BaseReportAgent):
    key           = "financial_risk"
    prompt_label  = "RED FLAGS FINDINGS"
    pattern       = ExecutionPattern.MAP_REDUCE
    output_schema = FinancialRiskPerYearOutput  # map phase: per-document
    reduce_schema = FinancialRiskOutput         # reduce phase: cross-period verdict
    system_prompt = """
You are an expert in detecting financial reporting manipulation, trained in Howard Schilit's
"Financial Shenanigans".

Look for:
- Revenue manipulation: channel stuffing, round-tripping, premature recognition
- Expense manipulation: aggressive capitalisation, cookie jar reserves
- Balance sheet inflation: off-balance-sheet liabilities, goodwill impairment avoidance
- Cash flow shenanigans: misclassification between operating/investing/financing
- Warning signals: auditor changes, restatements, related-party transactions,
  non-GAAP metrics that diverge sharply from GAAP

If you find no red flags, say so directly. Do not manufacture concerns.
""".strip()

    def select_documents(self, bundle: ContextBundle) -> list[DocumentContext]:
        return bundle.get_documents(types=[
            DocumentType.ANNUAL_REPORT,
            DocumentType.QUARTERLY_REPORT,
        ])

    def build_user_message(self, document: DocumentContext, bundle: ContextBundle) -> str:
        return f"""Identify financial red flags for {bundle.company_name} ({bundle.qfs_symbol}) \
for the period covered by this document.

## DOCUMENT: {document.file_name} ({document.document_type})
{document.raw_markdown}

## FINANCIAL METRICS
{self.select_financial_metrics(bundle) or "Not yet available — base your analysis on the document."}

Provide a per-period financial risk assessment. Identify the fiscal year from the document \
and include it in the fiscal_year field. If no red flags exist, say so explicitly.
"""

    def build_reduce_message(self, map_outputs, bundle: ContextBundle) -> str:
        per_year_json = json.dumps([o.model_dump() for o in map_outputs], indent=2)
        return f"""You have completed per-period financial risk analysis for \
{bundle.company_name} ({bundle.qfs_symbol}).

## PER-PERIOD FINDINGS
{per_year_json}

Synthesise these findings into a cross-period verdict:
- Are red flags isolated to a single period or recurring (suggesting a structural pattern)?
- Has manipulation risk increased or decreased over time?
- What is the overall manipulation risk rating?

Provide the integrated financial risk assessment.
"""
