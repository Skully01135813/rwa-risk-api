from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="RWA AI Risk Analyst",
    version="1.0.0",
)


class RiskRequest(BaseModel):
    portfolioId: str
    portfolioName: str
    previousValuation: float
    currentValuation: float
    debt: float
    previousLTV: float
    currentLTV: float
    riskThreshold: float
    valuationConfidence: float
    riskTriggered: bool


class RiskResponse(BaseModel):
    riskLevel: str
    summary: str
    thresholdBreach: float
    recommendedAction: str
    requiresHumanReview: bool


@app.get("/")
def root():
    return {
        "service": "RWA AI Risk Analyst",
        "status": "running",
    }


@app.post("/analyze", response_model=RiskResponse)
def analyze_risk(data: RiskRequest):
    threshold_breach = max(
        data.currentLTV - data.riskThreshold,
        0,
    )

    valuation_change = (
        (data.currentValuation - data.previousValuation)
        / data.previousValuation
    ) * 100

    if data.riskTriggered:
        risk_level = "HIGH"

        summary = (
            f"{data.portfolioName} valuation changed by "
            f"{valuation_change:.2f}%. "
            f"LTV increased from {data.previousLTV:.2f}% "
            f"to {data.currentLTV:.2f}%, exceeding the "
            f"{data.riskThreshold:.2f}% risk threshold."
        )

        recommended_action = (
            "Review the collateral position, confirm the "
            "valuation source, and consider deleveraging "
            "or adding collateral."
        )

        requires_human_review = True

    else:
        risk_level = "LOW"

        summary = (
            f"{data.portfolioName} remains within the "
            f"configured risk threshold."
        )

        recommended_action = (
            "Continue monitoring the portfolio."
        )

        requires_human_review = False

    return RiskResponse(
        riskLevel=risk_level,
        summary=summary,
        thresholdBreach=round(threshold_breach, 2),
        recommendedAction=recommended_action,
        requiresHumanReview=requires_human_review,
    )