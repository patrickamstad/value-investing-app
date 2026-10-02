from ..llm.schemas import DocumentType
from .base import BaseReportAgent, ExecutionPattern
from .context_bundle import ContextBundle, DocumentContext
from .schemas import GuidanceOutput


class GuidanceAgent(BaseReportAgent):
    key           = "guidance"
    prompt_label  = "GUIDANCE FINDINGS"
    pattern       = ExecutionPattern.MULTI_SOURCE_SYNTHESIS
    output_schema = GuidanceOutput
    system_prompt = """
You are an expert in evaluating management guidance and forward-looking statements.

Assess:
- Historical guidance accuracy: does management sandbag (consistently beats) or over-promise?
- Current forward guidance: revenue growth, margin trajectory, capex plans
- Key assumptions underlying guidance (macro, pricing, competitive assumptions)
- Any guidance withdrawal, unusual vagueness, or narrowing of disclosure
- Earnings call tone: confident and specific vs. defensive and evasive

Pay more attention to what management avoids discussing than what they emphasise.
Be sceptical of management optimism without evidence.
""".strip()

    def select_documents(self, bundle: ContextBundle) -> list[DocumentContext]:
        return (
            bundle.get_documents(types=[DocumentType.EARNINGS_CALL], latest_n=1)
            + bundle.get_documents(types=[DocumentType.ANNUAL_REPORT], latest_n=1)
            + bundle.get_documents(types=[DocumentType.ANALYST_REPORT])
            + bundle.get_documents(types=[DocumentType.INVESTOR_PRESENTATION], latest_n=1)
        )

    def build_synthesis_message(
        self,
        documents: list[DocumentContext],
        bundle: ContextBundle,
    ) -> str:
        if not documents:
            doc_blocks = "No documents available."
        else:
            doc_blocks = "\n\n---\n\n".join(
                f"### {d.file_name} ({d.document_type})\n\n{d.raw_markdown}"
                for d in documents
            )

        return f"""Assess management guidance for {bundle.company_name} ({bundle.qfs_symbol}).

## RESEARCH DOCUMENTS
{doc_blocks}

## FINANCIAL METRICS
{self.select_financial_metrics(bundle) or "Not yet available — base your analysis on the documents."}

Provide a structured guidance assessment.
"""
