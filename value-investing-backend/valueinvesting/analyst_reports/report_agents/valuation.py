from ..llm.schemas import DocumentType
from .base import BaseReportAgent, ExecutionPattern
from .context_bundle import ContextBundle, DocumentContext
from .schemas import ValuationOutput


class ValuationAgent(BaseReportAgent):
    key           = "valuation"
    prompt_label  = "COMPUTED VALUATION"
    pattern       = ExecutionPattern.SINGLE_CALL
    output_schema = ValuationOutput
    system_prompt = """
You are an expert in fundamental valuation, trained in the Residual Operating Income (ReOI)
framework of Stephen Penman and the owner-earnings approach of Warren Buffett.

Assess:
- Current earnings power relative to cost of capital
- Return on Net Operating Assets (RNOA) and its sustainability
- Whether P/B and P/E multiples are justified by business quality
- Free cash flow yield and what growth rate is implied by the current price
- Margin of safety: at what price does this become attractive?

Use a range of methods where data supports it. Be explicit about assumptions.
If data is insufficient for a precise estimate, provide a qualitative range.
""".strip()

    def select_documents(self, bundle: ContextBundle) -> list[DocumentContext]:
        return bundle.get_documents(types=[DocumentType.ANNUAL_REPORT], latest_n=1)

    def build_user_message(self, document: DocumentContext, bundle: ContextBundle) -> str:
        return f"""Assess the valuation of {bundle.company_name} ({bundle.qfs_symbol}).

## RESEARCH DOCUMENTS
{bundle.raw_docs(types=[DocumentType.ANNUAL_REPORT, DocumentType.ANALYST_REPORT])}

## FINANCIAL METRICS
{self.select_financial_metrics(bundle) or "Not yet available — base your analysis on the documents."}

## SAVED VALUATION MODEL
{bundle.valuation_data or "Not yet available — base your analysis on the documents."}

Provide a structured valuation assessment.
"""
