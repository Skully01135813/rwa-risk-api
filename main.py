from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="RWA AI Risk Analyst",
    version="1.1.0",
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
        "version": "1.1.0",
    }


@app.post("/analyze", response_model=RiskResponse)
def analyze_risk(data: RiskRequest):
    threshold_breach = max(
        data.currentLTV - data.riskThreshold,
        0,
    )

    valuation_change = (
        (
            data.currentValuation
            - data.previousValuation
        )
        / data.previousValuation
    ) * 100

    ltv_change = (
        data.currentLTV
        - data.previousLTV
    )

    # ------------------------------------------------
    # CASE 1:
    # Risk threshold is breached
    # ------------------------------------------------

    if data.riskTriggered:
        risk_level = "HIGH"
        requires_human_review = True

        # --------------------------------------------
        # New or changed risk event
        # --------------------------------------------

        if abs(valuation_change) >= 0.01:
            summary = (
                f"{data.portfolioName} has entered or changed "
                f"a high-risk condition. "
                f"The portfolio valuation changed by "
                f"{valuation_change:.2f}% from "
                f"${data.previousValuation:,.0f} to "
                f"${data.currentValuation:,.0f}. "
                f"LTV changed from "
                f"{data.previousLTV:.2f}% to "
                f"{data.currentLTV:.2f}%. "
                f"The current LTV exceeds the "
                f"{data.riskThreshold:.2f}% threshold by "
                f"{threshold_breach:.2f} percentage points."
            )

            recommended_action = (
                "Confirm the latest valuation source, review "
                "collateral adequacy, and assess whether "
                "deleveraging or additional collateral is required."
            )

        # --------------------------------------------
        # Ongoing risk condition
        # --------------------------------------------

        else:
            summary = (
                f"{data.portfolioName} remains in a high-risk "
                f"condition. "
                f"The latest external valuation of "
                f"${data.currentValuation:,.0f} matches the "
                f"current on-chain valuation. "
                f"LTV remains at "
                f"{data.currentLTV:.2f}%, which exceeds the "
                f"{data.riskThreshold:.2f}% threshold by "
                f"{threshold_breach:.2f} percentage points. "
                f"No valuation update is required at this time."
            )

            recommended_action = (
                "Continue active monitoring and review the "
                "collateral position. Consider deleveraging "
                "or adding collateral while the LTV remains "
                "above the configured threshold."
            )

    # ------------------------------------------------
    # CASE 2:
    # Portfolio is within threshold
    # ------------------------------------------------

    else:
        risk_level = "LOW"
        requires_human_review = False

        if abs(valuation_change) >= 0.01:
            summary = (
                f"{data.portfolioName} remains within the "
                f"configured risk threshold. "
                f"The valuation changed by "
                f"{valuation_change:.2f}% and LTV changed by "
                f"{ltv_change:.2f} percentage points to "
                f"{data.currentLTV:.2f}%. "
                f"The current threshold is "
                f"{data.riskThreshold:.2f}%."
            )

        else:
            summary = (
                f"{data.portfolioName} remains within the "
                f"configured risk threshold. "
                f"The latest valuation matches the current "
                f"on-chain valuation and LTV remains at "
                f"{data.currentLTV:.2f}%."
            )

        recommended_action = (
            "Continue normal portfolio monitoring."
        )

    return RiskResponse(
        riskLevel=risk_level,
        summary=summary,
        thresholdBreach=round(
            threshold_breach,
            2,
        ),
        recommendedAction=recommended_action,
        requiresHumanReview=requires_human_review,
    )