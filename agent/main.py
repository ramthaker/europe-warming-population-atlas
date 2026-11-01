"""Strands API for map-grounded community heat-preparedness briefs."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from strands import Agent, tool
from strands.models import BedrockModel

load_dotenv(Path(__file__).with_name(".env"))

WHO_HEAT_GUIDANCE = (
    "WHO/Europe, #KeepCool in the heat (8 June 2026): "
    "https://www.who.int/europe/news-room/fact-sheets/item/keepcool-in-the-heat"
)


class CellContext(BaseModel):
    cell_id: str = Field(min_length=1, max_length=80)
    scenario: Literal["rcp45", "rcp85"]
    period: Literal["mid", "late"]
    p10_c: float
    median_c: float
    p90_c: float
    population_2020: int = Field(ge=0)

    @field_validator("cell_id")
    @classmethod
    def safe_cell_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", value):
            raise ValueError("Cell ID contains unsupported characters")
        return value

    @field_validator("p10_c", "median_c", "p90_c")
    @classmethod
    def finite_temperature(cls, value: float) -> float:
        if not math.isfinite(value) or value < -20 or value > 30:
            raise ValueError("Temperature change is outside the supported range")
        return value

    @model_validator(mode="after")
    def ordered_ensemble_range(self) -> "CellContext":
        if not self.p10_c <= self.median_c <= self.p90_c:
            raise ValueError("Expected p10 <= median <= p90")
        return self


class BriefRequest(BaseModel):
    question: str = Field(min_length=8, max_length=700)
    cell: CellContext


class BriefResponse(BaseModel):
    brief: str
    model_id: str
    evidence: CellContext


app = FastAPI(title="Climate Atlas Resilience Agent", version="0.1.0")
web_origin = os.getenv("WEB_ORIGIN", "http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[web_origin, "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ready", "agent": "strands", "model": os.getenv("STRANDS_MODEL_ID", "eu.amazon.nova-lite-v1:0")}


def make_evidence_tool(cell: CellContext):
    """Bind a per-request, validated cell snapshot into a read-only Strands tool."""

    @tool
    def read_selected_map_cell() -> str:
        """Return the exact selected map cell values and their interpretation limits.

        Call this before describing the location's scenario values. The estimate
        is an annual-mean model anomaly and the population is a 2020 grid total.
        """
        return json.dumps(
            {
                **cell.model_dump(),
                "scenario_label": "RCP 4.5" if cell.scenario == "rcp45" else "RCP 8.5",
                "period_label": "2041–2060" if cell.period == "mid" else "2081–2100",
                "baseline": "1981–2000",
                "dataset": "EURO-CORDEX CMIP5 matched-model ensemble + GHSL GHS-POP 2020",
                "limits": [
                    "Conditional scenario, not a forecast or probability-ranked prediction.",
                    "Annual mean does not describe heatwaves, daily extremes, or urban heat islands.",
                    "Population count is aggregated to a climate-model cell; it is not a count of vulnerable people or individual exposure.",
                ],
            },
            ensure_ascii=False,
        )

    return read_selected_map_cell


@tool
def get_community_heat_actions() -> str:
    """Return general, non-clinical community heat-preparedness actions from WHO guidance."""
    return json.dumps(
        {
            "source": WHO_HEAT_GUIDANCE,
            "actions": [
                "Prepare a locally verified list of cool public places, their opening hours, accessibility, and transport options.",
                "Coordinate opt-in check-ins through existing community groups for neighbors who may need help during hot weather.",
                "Share clear local instructions on where to find official heat warnings and how residents can request support.",
                "Agree who will maintain contacts and refresh venue and service information before each summer season.",
            ],
            "boundary": "These are planning prompts, not clinical advice, an emergency warning, or a substitute for local health authority guidance.",
        },
        ensure_ascii=False,
    )


SYSTEM_PROMPT = """You are the Climate Atlas Community Resilience Agent. Help a community group turn the selected Europe climate-map cell into a short, practical heat-preparedness planning brief.

Before answering, call both tools: read_selected_map_cell and get_community_heat_actions. Use the exact values returned by the cell tool. Include the scenario, period, annual-mean warming median and 10th–90th range, and 2020 population. Then give 3-4 practical planning steps and identify one useful local fact the group should verify (for example, cooling venue capacity or accessible transport).

Return only the finished, user-facing brief. Never reveal internal reasoning or planning, and never include tags such as <thinking>, <analysis>, or <reasoning>. Do not use bracketed placeholders; address the reader as "your community" when no group name is provided.

Format the response in Markdown: a short title; a compact climate snapshot; three practical numbered steps; one local fact to verify; and a brief limits note ending with the WHO/Europe source link returned by the guidance tool. Keep it under 180 words and avoid horizontal rules.

Describe warming as a conditional model scenario, not a statement about what will happen. Prefer "In this scenario, the ensemble median annual-mean change is …" and never say "your community will" or "is projected to experience" the warming. Label population as a 2020 estimate aggregated to the selected climate grid cell; do not present it as a community census or a count of exposed people.

Always distinguish long-term model scenarios from current weather and official heat alerts. Never call the population count a vulnerable-person count, infer health outcomes, diagnose, prescribe, or claim a site has a cooling center or service unless the provided data says so. Do not calculate a health risk score. If the user asks for immediate danger or medical instructions, direct them to local emergency services and their health authority without inventing contact details."""


def clean_agent_brief(value: str) -> str:
    """Remove model reasoning tags and unfinished template wording before display."""
    for tag in ("thinking", "analysis", "reasoning"):
        value = re.sub(
            rf"<{tag}\b[^>]*>.*?</{tag}\s*>",
            "",
            value,
            flags=re.IGNORECASE | re.DOTALL,
        )
        value = re.sub(
            rf"<{tag}\b[^>]*>.*\Z",
            "",
            value,
            flags=re.IGNORECASE | re.DOTALL,
        )
        value = re.sub(rf"</?{tag}\b[^>]*>", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\[community group\]", "your community", value, flags=re.IGNORECASE)
    value = re.sub(r"(?m)^\s*---+\s*$", "", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


@app.post("/api/brief", response_model=BriefResponse)
def create_brief(request: BriefRequest) -> BriefResponse:
    model_id = os.getenv("STRANDS_MODEL_ID", "eu.amazon.nova-lite-v1:0")
    region = os.getenv("STRANDS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-central-1"))
    try:
        model = BedrockModel(
            model_id=model_id,
            region_name=region,
            max_tokens=1200,
            temperature=0.2,
        )
        agent = Agent(
            model=model,
            tools=[make_evidence_tool(request.cell), get_community_heat_actions],
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None,
        )
        result = agent(request.question)
        brief = clean_agent_brief(str(result))
        return BriefResponse(brief=brief, model_id=model_id, evidence=request.cell)
    except Exception as error:  # noqa: BLE001 - translate provider errors for the UI
        # Keep prompts out of logs while recording actionable provider diagnostics.
        if isinstance(error, ClientError):
            provider_error = error.response.get("Error", {})
            detail = str(provider_error.get("Message", ""))[:500]
            print(f"Strands provider failure ({provider_error.get('Code', 'ClientError')}): {detail}")
        else:
            print(f"Strands request failed ({type(error).__name__}).")
        raise HTTPException(
            status_code=503,
            detail="The resilience agent could not reach its model. Check AWS credentials, region, and Bedrock model access.",
        ) from None
