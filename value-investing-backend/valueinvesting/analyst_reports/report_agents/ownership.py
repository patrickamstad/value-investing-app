from ..llm.schemas import DocumentType
from .base import BaseReportAgent, ExecutionPattern
from .context_bundle import ContextBundle, DocumentContext
from .schemas import OwnershipOutput


class OwnershipAgent(BaseReportAgent):
    key           = "ownership"
    prompt_label  = "OWNERSHIP & INSIDER DATA"
    pattern       = ExecutionPattern.SINGLE_CALL
    output_schema = OwnershipOutput
    system_prompt = """
You are an expert in analysing corporate ownership structure and insider behaviour.

Assess:
- Insider buying/selling: open-market buying at current prices = strong alignment signal;
  heavy selling beyond diversification = warning
- Skin in the game: do insiders hold meaningful stakes relative to compensation?
- Institutional quality: are major holders long-term value investors or momentum/index funds?
- Ownership concentration: aligned control vs. entrenchment risk
- Any blockholder activism or pressure for strategic change

If insider or ownership data is unavailable, say so explicitly rather than speculating.
""".strip()

    def select_documents(self, bundle: ContextBundle) -> list[DocumentContext]:
        return bundle.get_documents(types=[DocumentType.ANNUAL_REPORT], latest_n=1)

    def build_user_message(self, document: DocumentContext, bundle: ContextBundle) -> str:
        return f"""Assess ownership and insider activity for {bundle.company_name} ({bundle.qfs_symbol}).

## RESEARCH DOCUMENTS
{bundle.raw_docs(types=[DocumentType.ANNUAL_REPORT])}

## INSIDER TRANSACTION DATA
{bundle.insider_data or "Not yet available."}

## SHAREHOLDER STRUCTURE
{bundle.shareholder_data or "Not yet available."}

Provide a structured ownership assessment.
"""
