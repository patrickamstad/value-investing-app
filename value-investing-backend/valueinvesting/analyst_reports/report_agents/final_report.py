import json

from .context_bundle import ContextBundle
from .registry import AGENT_REGISTRY
from .schemas import AnalystReportSections

ASSEMBLY_SYSTEM_PROMPT = """
You are a senior analyst writing a definitive investment report for a professional value investor.
Your doctrine:
- Every claim must be traceable to the findings provided.
- If findings conflict, surface the tension — do not paper over it.
- Do not manufacture conviction the findings do not support.
- Tone: disciplined, intellectually honest, no hype, no hedging into meaninglessness.
- Write in clear prose. Avoid bullets within sections; these are paragraphs, not lists.
""".strip()

ASSEMBLY_PROMPT_TEMPLATE = """
You are writing the final integrated analyst report for {company_name}.

{findings_sections}

Produce the report with these sections in order:
1. executive_summary — 4-6 sentences: most important takeaway + core thesis
2. business_overview — what the company does, informed by competitive position findings
3. shareholder_structure — ownership concentration and insider signals
4. competitive_advantage — honest moat assessment
5. earnings_quality_and_red_flags — combine both inputs; lead with most material concern
6. valuation — discuss assumptions and margin of safety, not arithmetic
7. guidance — forward outlook with scepticism where warranted
8. risks — the 3-5 risks that actually matter, not a generic list
9. why_opportunity_exists — be honest if there is no clear reason
10. catalysts — concrete, time-boundable where possible

Rules:
- Base every claim on the findings above. Do not introduce outside information.
- If sections disagree, surface the tension rather than resolving it artificially.
- Do not manufacture conviction the findings do not support.
""".strip()


class FinalAnalystReportAgent:
    def run(self, bundle: ContextBundle, provider, agent_outputs: dict[str, dict]) -> dict:
        findings_sections = "\n\n".join(
            f"[{agent_cls.prompt_label}]:\n{json.dumps(agent_outputs[agent_cls.key], indent=2)}"
            for agent_cls in AGENT_REGISTRY
            if agent_cls.key in agent_outputs
        )

        user_message = ASSEMBLY_PROMPT_TEMPLATE.format(
            company_name=bundle.company_name,
            findings_sections=findings_sections,
        )

        return provider.run_agent(
            user_message=user_message,
            system_prompt=ASSEMBLY_SYSTEM_PROMPT,
            schema=AnalystReportSections,
        )
