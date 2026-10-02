from .earnings_quality import EarningsQualityAgent
from .financial_risk import FinancialRiskAgent
from .valuation import ValuationAgent
from .competitive_position import CompetitivePositionAgent
from .capital_allocation import CapitalAllocationAgent
from .ownership import OwnershipAgent
from .guidance import GuidanceAgent

# To add a new agent:
# 1. Create a new file implementing BaseReportAgent
# 2. Import it here and append to AGENT_REGISTRY
AGENT_REGISTRY = [
    EarningsQualityAgent,
    FinancialRiskAgent,
    ValuationAgent,
    CompetitivePositionAgent,
    CapitalAllocationAgent,
    OwnershipAgent,
    GuidanceAgent,
]
