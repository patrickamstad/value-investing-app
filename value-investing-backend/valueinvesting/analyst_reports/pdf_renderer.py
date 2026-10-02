import markdown as md_lib
import weasyprint

_SECTION_LABELS = {
    "executive_summary":              "Executive Summary",
    "business_overview":              "Business Overview",
    "shareholder_structure":          "Shareholder Structure",
    "competitive_advantage":          "Competitive Advantage",
    "earnings_quality_and_red_flags": "Earnings Quality & Red Flags",
    "valuation":                      "Valuation",
    "guidance":                       "Management Guidance",
    "risks":                          "Risks",
    "why_opportunity_exists":         "Why the Opportunity Exists",
    "catalysts":                      "Catalysts",
}

_CSS = """
body  { font-family: sans-serif; font-size: 11pt; color: #1a1a2e; margin: 0; }
.cover { background: #1a1a2e; color: #fff; padding: 80px 60px; }
.cover h1 { font-size: 28pt; margin: 0 0 8px 0; }
.cover .subtitle { font-size: 12pt; color: #a0aec0; }
.content { padding: 48px 60px; }
section { margin-bottom: 36px; page-break-inside: avoid; }
h2 { font-size: 14pt; font-weight: 700; border-bottom: 2px solid #e2e8f0;
     padding-bottom: 6px; margin-bottom: 12px; }
p  { line-height: 1.7; margin: 0 0 10px 0; }
"""


def render_report_to_pdf(sections: dict, company_name: str) -> bytes:
    sections_html = ""
    for key, label in _SECTION_LABELS.items():
        content_html = md_lib.markdown(sections.get(key, ""))
        sections_html += f"<section><h2>{label}</h2>{content_html}</section>\n"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_CSS}</style></head>
<body>
  <div class="cover">
    <h1>{company_name}</h1>
    <div class="subtitle">Analyst Report — Value Investing Framework</div>
  </div>
  <div class="content">{sections_html}</div>
</body></html>"""

    return weasyprint.HTML(string=html).write_pdf()
