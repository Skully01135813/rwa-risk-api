from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()


# -------------------------
# Request Schema
# -------------------------
class AssetInput(BaseModel):
    purchasePrice: float
    monthlyRent: float
    annualExpenses: float
    vacancyRate: float  # 0–1
    locationScore: float  # 0–10
    marketTrend: float  # -1 to +1
    propertyTypeScore: float  # 0–1
    daysOnMarket: int
    LTV: Optional[float] = 0.0  # 0–1


# -------------------------
# Utility Functions
# -------------------------
def clamp(value, min_val=0, max_val=100):
    return max(min_val, min(value, max_val))


def normalize(value, min_val, max_val):
    if max_val - min_val == 0:
        return 0
    return clamp((value - min_val) / (max_val - min_val), 0, 1)


# -------------------------
# Core Risk Calculation
# -------------------------
def calculate_risk(data: AssetInput):

    # ---- Yield Calculation ----
    annual_income = data.monthlyRent * 12
    net_income = annual_income - data.annualExpenses

    if data.purchasePrice == 0:
        yield_rate = 0
    else:
        yield_rate = net_income / data.purchasePrice

    normalized_yield = normalize(yield_rate, 0.02, 0.10)

    expense_ratio = (
        data.annualExpenses / annual_income if annual_income > 0 else 0
    )

    # ---- Income Risk ----
    income_risk = (
        50 * data.vacancyRate +
        30 * (1 - normalized_yield) +
        20 * expense_ratio
    )

    # ---- Market Risk ----
    market_risk = (
        60 * (1 - data.locationScore / 10) +
        40 * (1 - (data.marketTrend + 1) / 2)
    )

    # ---- Liquidity Risk ----
    normalized_dom = clamp(data.daysOnMarket / 180, 0, 1)

    liquidity_risk = (
        70 * (1 - data.propertyTypeScore) +
        30 * normalized_dom
    )

    # ---- Leverage Risk ----
    leverage_risk = clamp(data.LTV * 100, 0, 100)

    # ---- Final Risk Score ----
    final_risk = (
        0.35 * income_risk +
        0.25 * market_risk +
        0.20 * liquidity_risk +
        0.20 * leverage_risk
    )

    final_risk = clamp(final_risk, 0, 100)

    # ---- Confidence Score ----
    total_fields = 8
    missing = sum([
        data.purchasePrice == 0,
        data.monthlyRent == 0,
        data.locationScore == 0,
        data.propertyTypeScore == 0
    ])
    confidence = 1 - (missing / total_fields)

    return {
        "riskScore": round(final_risk, 2),
        "yield": round(yield_rate * 100, 2),  # %
        "confidence": round(confidence, 2),
        "breakdown": {
            "incomeRisk": round(clamp(income_risk), 2),
            "marketRisk": round(clamp(market_risk), 2),
            "liquidityRisk": round(clamp(liquidity_risk), 2),
            "leverageRisk": round(clamp(leverage_risk), 2),
        }
    }


# -------------------------
# API Endpoint
# -------------------------
@app.post("/score")
def score_asset(asset: AssetInput):
    return calculate_risk(asset)
