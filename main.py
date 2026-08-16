import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel
from supabase import create_client, Client

load_dotenv()

app = FastAPI(
    title="RWA AI Risk Analyst",
    version="3.1.0",
)

openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SECRET_KEY")

if not supabase_url:
    raise RuntimeError(
        "SUPABASE_URL is not configured."
    )

if not supabase_key:
    raise RuntimeError(
        "SUPABASE_SECRET_KEY is not configured."
    )

supabase: Client = create_client(
    supabase_url,
    supabase_key,
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


class RiskHistoryItem(BaseModel):
    id: int
    portfolioId: str
    portfolioName: str
    valuation: float
    debt: float
    ltv: float
    riskThreshold: float
    thresholdBreach: float
    riskLevel: str
    riskTriggered: bool
    valuationConfidence: float | None
    aiSummary: str | None
    recommendedAction: str | None
    requiresHumanReview: bool
    createdAt: str


@app.get("/")
def root():
    return {
        "service": "RWA AI Risk Analyst",
        "status": "running",
        "version": "3.1.0",
        "aiEnabled": True,
        "historyEnabled": True,
    }


@app.get(
    "/history/{portfolio_id}",
    response_model=list[RiskHistoryItem],
)
def get_risk_history(
    portfolio_id: str,
):
    try:
        response = (
            supabase
            .table("risk_history")
            .select("*")
            .eq(
                "portfolio_id",
                portfolio_id,
            )
            .order(
                "created_at",
                desc=True,
            )
            .limit(50)
            .execute()
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Risk history query failed: {exc}",
        )

    history = []

    for row in response.data:
        history.append(
            RiskHistoryItem(
                id=row["id"],
                portfolioId=row["portfolio_id"],
                portfolioName=row["portfolio_name"],
                valuation=float(
                    row["valuation"]
                ),
                debt=float(
                    row["debt"]
                ),
                ltv=float(
                    row["ltv"]
                ),
                riskThreshold=float(
                    row["risk_threshold"]
                ),
                thresholdBreach=float(
                    row["threshold_breach"]
                ),
                riskLevel=row["risk_level"],
                riskTriggered=row["risk_triggered"],
                valuationConfidence=(
                    float(
                        row[
                            "valuation_confidence"
                        ]
                    )
                    if row[
                        "valuation_confidence"
                    ]
                    is not None
                    else None
                ),
                aiSummary=row["ai_summary"],
                recommendedAction=row[
                    "recommended_action"
                ],
                requiresHumanReview=row[
                    "requires_human_review"
                ],
                createdAt=row["created_at"],
            )
        )

    return history


@app.post(
    "/analyze",
    response_model=RiskResponse,
)
def analyze_risk(
    data: RiskRequest,
):
    threshold_breach = max(
        data.currentLTV
        - data.riskThreshold,
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
        response = (
            openai_client
            .responses
            .parse(
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

    history_row = {
        "portfolio_id":
            data.portfolioId,

        "portfolio_name":
            data.portfolioName,

        "valuation":
            data.currentValuation,

        "debt":
            data.debt,

        "ltv":
            data.currentLTV,

        "risk_threshold":
            data.riskThreshold,

        "threshold_breach":
            round(
                threshold_breach,
                2,
            ),

        "risk_level":
            risk_level,

        "risk_triggered":
            data.riskTriggered,

        "valuation_confidence":
            data.valuationConfidence,

        "ai_summary":
            analysis.summary,

        "recommended_action":
            analysis.recommendedAction,

        "requires_human_review":
            requires_human_review,
    }

    try:
        (
            supabase
            .table("risk_history")
            .insert(history_row)
            .execute()
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Risk history insert failed: {exc}",
        )

    return RiskResponse(
        riskLevel=risk_level,
        summary=analysis.summary,
        thresholdBreach=round(
            threshold_breach,
            2,
        ),
        recommendedAction=(
            analysis.recommendedAction
        ),
        requiresHumanReview=(
            requires_human_review
        ),
    )

@app.get(
    "/latest/{portfolio_id}",
    response_model=RiskHistoryItem,
)
def get_latest_risk_assessment(
    portfolio_id: str,
):
    try:
        response = (
            supabase
            .table("risk_history")
            .select("*")
            .eq(
                "portfolio_id",
                portfolio_id,
            )
            .order(
                "created_at",
                desc=True,
            )
            .limit(1)
            .execute()
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Latest risk query failed: {exc}",
        )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="No risk assessment found.",
        )

    row = response.data[0]

    return RiskHistoryItem(
        id=row["id"],
        portfolioId=row["portfolio_id"],
        portfolioName=row["portfolio_name"],
        valuation=float(
            row["valuation"]
        ),
        debt=float(
            row["debt"]
        ),
        ltv=float(
            row["ltv"]
        ),
        riskThreshold=float(
            row["risk_threshold"]
        ),
        thresholdBreach=float(
            row["threshold_breach"]
        ),
        riskLevel=row["risk_level"],
        riskTriggered=row["risk_triggered"],
        valuationConfidence=(
            float(
                row[
                    "valuation_confidence"
                ]
            )
            if row[
                "valuation_confidence"
            ]
            is not None
            else None
        ),
        aiSummary=row["ai_summary"],
        recommendedAction=row[
            "recommended_action"
        ],
        requiresHumanReview=row[
            "requires_human_review"
        ],
        createdAt=row["created_at"],
    )