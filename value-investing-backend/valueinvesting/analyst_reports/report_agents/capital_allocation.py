import json

from ..llm.schemas import DocumentType
from .base import BaseReportAgent, ExecutionPattern
from .context_bundle import ContextBundle, DocumentContext
from .schemas import CapitalAllocationOutput, CapitalAllocationPerYearOutput


class CapitalAllocationAgent(BaseReportAgent):
    key           = "capital_allocation"
    prompt_label  = "CAPITAL ALLOCATION FINDINGS"
    pattern       = ExecutionPattern.MAP_REDUCE
    output_schema = CapitalAllocationPerYearOutput  # map phase: per-document
    reduce_schema = CapitalAllocationOutput         # reduce phase: track record verdict
    system_prompt = """
You are an expert in evaluating management's capital allocation track record.

Assess:
- ROIC trend: above cost of capital and rising, stable, or declining?
- Buyback discipline: bought cheaply (price < intrinsic value) or just for EPS management?
- Dividend sustainability relative to free cash flow
- M&A track record: value-creating (ROIC > WACC on acquisitions) or value-destroying?
- Organic reinvestment quality: capex intensity, R&D productivity

Management that earns high returns on reinvested capital and returns excess cash sensibly
is a major positive. Excessive M&A at high prices, or buybacks at peak valuations, are
warning signs.
""".strip()

    def select_documents(self, bundle: ContextBundle) -> list[DocumentContext]:
        return bundle.get_documents(types=[
            DocumentType.ANNUAL_REPORT,
            DocumentType.QUARTERLY_REPORT,
        ])

    def build_user_message(self, document: DocumentContext, bundle: ContextBundle) -> str:
        return f"""Assess capital allocation for {bundle.company_name} ({bundle.qfs_symbol}) \
for the period covered by this document.

## DOCUMENT: {document.file_name} ({document.document_type})
{document.raw_markdown}

## FINANCIAL METRICS
{self.select_financial_metrics(bundle) or "Not yet available — base your analysis on the document."}

Provide a per-period capital allocation assessment. Identify the fiscal year from the document \
and include it in the fiscal_year field.
"""

    def build_reduce_message(self, map_outputs, bundle: ContextBundle) -> str:
        per_year_json = json.dumps([o.model_dump() for o in map_outputs], indent=2)
        return f"""You have completed per-period capital allocation analysis for \
{bundle.company_name} ({bundle.qfs_symbol}).

## PER-PERIOD FINDINGS
{per_year_json}

Synthesise these findings into a multi-year track record verdict:
- Is ROIC improving, stable, or declining over time?
- Has buyback and dividend discipline been consistent?
- What is the overall capital allocation quality assessment?

Provide the integrated capital allocation assessment.
"""
