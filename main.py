import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="RWA AI Risk Analyst",
    version="2.0.0",
)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
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


class AIRiskNarrative(BaseModel):
    summary: str
    recommendedAction: str


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
        "version": "2.0.0",
        "aiEnabled": True,
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

    if data.riskTriggered:
        risk_level = "HIGH"
        requires_human_review = True
    else:
        risk_level = "LOW"
        requires_human_review = False

    system_prompt = """
You are an RWA portfolio risk analyst.

The financial calculations, risk threshold, and risk classification
provided to you are trusted deterministic inputs from Chainlink CRE
and smart-contract state.

You must not recalculate, alter, override, or contradict those values.

Your job is only to explain the verified risk position and provide
a concise, conservative recommendation for human review.

Rules:
- Never invent financial values.
- Never change the supplied risk classification.
- Never claim a valuation changed if previous and current valuation are equal.
- If risk remains above threshold and valuation is unchanged, describe it as
  an ongoing risk condition.
- Do not instruct the system to execute blockchain transactions.
- Recommendations are advisory only.
- Keep the summary to a maximum of 4 sentences.
- Keep the recommended action to a maximum of 2 sentences.
- Do not use numbered lists or bullet points.
- Use plain professional English.
- Use standard ASCII punctuation only.
- Avoid special dashes, smart quotes, or unusual Unicode characters.
- Focus on the most important risk information rather than repeating every input.
"""

    user_prompt = f"""
Portfolio ID: {data.portfolioId}
Portfolio name: {data.portfolioName}

Previous valuation: ${data.previousValuation:,.0f}
Current valuation: ${data.currentValuation:,.0f}
Valuation change: {valuation_change:.2f}%

Debt: ${data.debt:,.0f}

Previous LTV: {data.previousLTV:.2f}%
Current LTV: {data.currentLTV:.2f}%

Risk threshold: {data.riskThreshold:.2f}%
Threshold breach: {threshold_breach:.2f} percentage points

Valuation confidence: {data.valuationConfidence:.2f}%

Risk triggered: {data.riskTriggered}
Risk level: {risk_level}
Human review required: {requires_human_review}
"""

    try:
        response = client.responses.parse(
            model="gpt-5-mini",
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            text_format=AIRiskNarrative,
        )

        analysis = response.output_parsed

        if analysis is None:
            raise RuntimeError(
                "Model returned no structured analysis."
            )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI analysis failed: {exc}",
        )

    return RiskResponse(
        riskLevel=risk_level,
        summary=analysis.summary,
        thresholdBreach=round(
            threshold_breach,
            2,
        ),
        recommendedAction=analysis.recommendedAction,
        requiresHumanReview=requires_human_review,
    )