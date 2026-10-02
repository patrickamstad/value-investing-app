from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ─── Shared enums ─────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW      = "low"
    MODERATE = "moderate"
    HIGH     = "high"


class QualityLevel(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class MoatDurability(str, Enum):
    WIDE   = "wide"
    NARROW = "narrow"
    NONE   = "none"


class InsiderTrend(str, Enum):
    BUYING  = "buying"
    SELLING = "selling"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class ManagementTone(str, Enum):
    OPTIMISTIC = "optimistic"
    CAUTIOUS   = "cautious"
    BALANCED   = "balanced"
    EVASIVE    = "evasive"


class PriceAssessment(str, Enum):
    OVERVALUED    = "overvalued"
    FAIRLY_VALUED = "fairly_valued"
    UNDERVALUED   = "undervalued"
    UNCERTAIN     = "uncertain"


# ─── Source attribution ────────────────────────────────────────────────────────

class EvidenceSource(BaseModel):
    document_name: str = Field(
        description="File name of the source document as provided."
    )
    page: Optional[int] = Field(
        default=None,
        description="Page number where this information was found, if identifiable.",
    )


class CitedFinding(BaseModel):
    finding: str = Field(
        description="The specific observation or fact extracted from the source material."
    )
    source: Optional[EvidenceSource] = Field(
        default=None,
        description="The document and page this finding was drawn from. Null only if the finding synthesises multiple sources.",
    )


# ─── Per-agent output schemas ──────────────────────────────────────────────────

class EarningsQualityOutput(BaseModel):
    overall_quality: QualityLevel = Field(
        description="Overall earnings quality rating based on accruals, cash conversion, and persistence."
    )
    cash_conversion: str = Field(
        description="Qualitative assessment of how reliably net income converts to free cash flow."
    )
    accruals_assessment: str = Field(
        description="Assessment of the accruals ratio and what it implies about earnings sustainability."
    )
    revenue_recognition_concerns: list[CitedFinding] = Field(
        description="Specific revenue recognition concerns identified. Empty list if none found."
    )
    key_findings: list[CitedFinding] = Field(
        description="The 3-5 most material earnings quality findings for the analyst report."
    )


class FinancialRiskOutput(BaseModel):
    manipulation_risk: RiskLevel = Field(
        description="Overall financial manipulation risk based on Schilit red-flag indicators."
    )
    red_flags: list[CitedFinding] = Field(
        description="Specific red flags identified. Empty list if none found."
    )
    accounting_concerns: list[CitedFinding] = Field(
        description="Accounting policy concerns (aggressive capitalisation, reserves, etc.). Empty list if none."
    )
    debt_risk_assessment: str = Field(
        description="Qualitative assessment of leverage, liquidity, and debt structure risk."
    )
    key_findings: list[CitedFinding] = Field(
        description="The 3-5 most material financial risk findings for the analyst report."
    )


class ValuationOutput(BaseModel):
    valuation_method: str = Field(
        description="Primary valuation method applied (e.g. ReOI, DCF, EV/EBIT multiples)."
    )
    estimated_intrinsic_value_range: Optional[str] = Field(
        default=None,
        description="Estimated intrinsic value range, e.g. '$120-140 per share'. Null if data is insufficient.",
    )
    current_price_assessment: PriceAssessment = Field(
        description="Whether the current market price appears overvalued, fairly valued, undervalued, or uncertain."
    )
    margin_of_safety: Optional[str] = Field(
        default=None,
        description="Estimated margin of safety at current price. Null if cannot be assessed.",
    )
    key_assumptions: list[CitedFinding] = Field(
        description="Critical assumptions the valuation rests on, each with its source."
    )
    key_findings: list[CitedFinding] = Field(
        description="The 3-5 most material valuation findings for the analyst report."
    )


class CompetitivePositionOutput(BaseModel):
    moat_exists: bool = Field(
        description="True if a durable competitive advantage is evidenced; false otherwise."
    )
    moat_type: Optional[str] = Field(
        default=None,
        description="Type of moat if present: 'switching costs', 'network effects', 'cost advantage', 'intangible assets', 'efficient scale'. Null if no moat.",
    )
    moat_durability: MoatDurability = Field(
        description="Width of the moat: wide (20+ year durability), narrow (5-10 years), or none."
    )
    competitive_threats: list[CitedFinding] = Field(
        description="Key competitive threats identified, each with its source."
    )
    key_findings: list[CitedFinding] = Field(
        description="The 3-5 most material competitive position findings for the analyst report."
    )


class CapitalAllocationOutput(BaseModel):
    roic_assessment: str = Field(
        description="Trend and level of ROIC relative to cost of capital."
    )
    buyback_quality: str = Field(
        description="Assessment of buyback discipline — bought cheaply or for EPS management?"
    )
    dividend_sustainability: str = Field(
        description="Assessment of dividend sustainability relative to free cash flow."
    )
    ma_track_record: Optional[str] = Field(
        default=None,
        description="M&A track record — value-creating or value-destroying? Null if no significant M&A.",
    )
    key_findings: list[CitedFinding] = Field(
        description="The 3-5 most material capital allocation findings for the analyst report."
    )


class OwnershipOutput(BaseModel):
    insider_trend: InsiderTrend = Field(
        description="Net direction of insider open-market transactions over the last 12 months."
    )
    insider_skin_in_game: str = Field(
        description="Assessment of whether insiders hold meaningful ownership stakes relative to compensation."
    )
    institutional_quality: str = Field(
        description="Assessment of whether major institutional holders are long-term value investors or short-term/index funds."
    )
    concentration_risk: str = Field(
        description="Assessment of ownership concentration and whether it represents alignment or entrenchment risk."
    )
    key_findings: list[CitedFinding] = Field(
        description="The 3-5 most material ownership findings for the analyst report."
    )


class GuidanceOutput(BaseModel):
    guidance_reliability: str = Field(
        description="Historical accuracy of management guidance — do they sandbag or over-promise?"
    )
    management_tone: ManagementTone = Field(
        description="Overall tone on the most recent earnings call or investor presentation."
    )
    key_guidance_points: list[CitedFinding] = Field(
        description="The most important forward-looking statements management has made, each with source."
    )
    guidance_risks: list[CitedFinding] = Field(
        description="Key risks to management's stated guidance being achieved."
    )
    key_findings: list[CitedFinding] = Field(
        description="The 3-5 most material guidance findings for the analyst report."
    )


# ─── MAP_REDUCE per-document (map-phase) schemas ──────────────────────────────

class EarningsQualityPerYearOutput(BaseModel):
    fiscal_year: str = Field(
        description="Fiscal year or period this analysis covers, e.g. 'FY2023'."
    )
    cash_conversion: str = Field(
        description="How reliably net income converted to free cash flow this year."
    )
    accruals_assessment: str = Field(
        description="Accruals ratio assessment and what it implies about earnings sustainability this year."
    )
    revenue_recognition_concerns: list[CitedFinding] = Field(
        description="Revenue recognition concerns identified this year. Empty list if none."
    )
    key_findings: list[CitedFinding] = Field(
        description="The 2-3 most material earnings quality observations for this year."
    )


class FinancialRiskPerYearOutput(BaseModel):
    fiscal_year: str = Field(
        description="Fiscal year or period this analysis covers, e.g. 'FY2023'."
    )
    red_flags: list[CitedFinding] = Field(
        description="Schilit red flags identified this year. Empty list if none."
    )
    accounting_concerns: list[CitedFinding] = Field(
        description="Accounting policy concerns identified this year. Empty list if none."
    )
    debt_risk_assessment: str = Field(
        description="Leverage and debt structure risk assessment for this year."
    )
    key_findings: list[CitedFinding] = Field(
        description="The 2-3 most material financial risk observations for this year."
    )


class CapitalAllocationPerYearOutput(BaseModel):
    fiscal_year: str = Field(
        description="Fiscal year or period this analysis covers, e.g. 'FY2023'."
    )
    roic_assessment: str = Field(
        description="ROIC trend and level relative to cost of capital this year."
    )
    buyback_quality: str = Field(
        description="Assessment of buyback discipline and timing this year."
    )
    dividend_sustainability: str = Field(
        description="Dividend coverage and sustainability assessment this year."
    )
    ma_track_record: Optional[str] = Field(
        default=None,
        description="M&A activity and value creation this year. Null if none."
    )
    key_findings: list[CitedFinding] = Field(
        description="The 2-3 most material capital allocation observations for this year."
    )


# ─── Final assembly output ─────────────────────────────────────────────────────

class AnalystReportSections(BaseModel):
    executive_summary: str = Field(
        description="4-6 sentence synthesis: the single most important takeaway and core investment thesis."
    )
    business_overview: str = Field(
        description="What the company does, its revenue segments, and market position."
    )
    shareholder_structure: str = Field(
        description="Ownership concentration, insider buying/selling, and what it signals about alignment."
    )
    competitive_advantage: str = Field(
        description="Honest assessment of whether a durable moat exists and what sustains or threatens it."
    )
    earnings_quality_and_red_flags: str = Field(
        description="Combined earnings quality and financial risk narrative. Lead with the most material concern."
    )
    valuation: str = Field(
        description="Narrative on the valuation — discuss assumptions and margin of safety, not arithmetic."
    )
    guidance: str = Field(
        description="Management's forward outlook with appropriate scepticism where warranted."
    )
    risks: str = Field(
        description="The 3-5 risks that actually matter for this specific company. Not a generic list."
    )
    why_opportunity_exists: str = Field(
        description="Honest explanation of why the market may be mispricing this. State clearly if there is no obvious reason."
    )
    catalysts: str = Field(
        description="Concrete, time-boundable events or developments that could unlock value."
    )
