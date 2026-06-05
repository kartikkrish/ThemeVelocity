"""FastAPI response schemas (Pydantic v2)."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel


class ThemeHeat(BaseModel):
    theme_id: str
    name: str
    composite_score: float
    source_diversity: int
    earliness: float
    breaching: bool
    ts: str
    # Phase 2 additions — nullable until synthesis runs
    one_line_thesis: str | None = None
    catalyst_type: str | None = None
    maturity_stage: str | None = None


class VelocityPoint(BaseModel):
    ts: str
    composite_score: float
    source_diversity: int
    earliness: float
    breaching: bool


class SourceSnapshot(BaseModel):
    source: str
    zscore: float
    cusum: float
    velocity: float
    acceleration: float
    count_1d: int


class ConfidenceData(BaseModel):
    c_velocity: float
    c_source: float
    c_catalyst: float
    c_earliness: float
    c_linkage: float
    c_liquidity: float
    c_total: float
    epistemic_tag: str  # V / E / I


class BeneficiaryNode(BaseModel):
    node_role: str           # direct / first_order / second_order / proxy
    company_name: str
    ticker: str
    exchange: str
    linkage_tightness: str   # tight / moderate / loose
    justification: str
    epistemic_tag: str


class SynthesisData(BaseModel):
    one_line_thesis: str
    catalyst_type: str
    catalyst_detail: str
    maturity_stage: str
    is_real_theme: bool
    key_entities: list[str]
    epistemic_tag: str
    noise_reason: str | None = None


class ThemeDetail(BaseModel):
    theme_id: str
    name: str
    primitive: str | None
    status: str
    composite_score: float
    source_diversity: int
    earliness: float
    breaching: bool
    per_source: list[SourceSnapshot]
    velocity_history: list[VelocityPoint]
    # Phase 2+
    synthesis: SynthesisData | None = None
    confidence: ConfidenceData | None = None
    beneficiaries: list[BeneficiaryNode] = []


class AlertItem(BaseModel):
    alert_id: str
    theme_id: str
    theme_name: str = ""
    fired_at: str
    composite_score: float
    one_line_thesis: str | None = None
    acknowledged: bool


class IngestionStatus(BaseModel):
    status: str
    counts: dict[str, int]


class ModelSettingsResponse(BaseModel):
    provider: str
    api_key_set: bool
    api_key_masked: str | None  # e.g. "sk-ant-...a1b2"
    base_url: str
    synthesis_model: str
    value_chain_model: str


class ModelSettingsUpdate(BaseModel):
    provider: str
    api_key: str | None = None   # None = keep existing; "" = clear
    base_url: str = ""
    synthesis_model: str
    value_chain_model: str


class ModelTestResult(BaseModel):
    ok: bool
    message: str
