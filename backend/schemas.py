# schemas.py — /api/farewell/recommendations の入力と出力の形（要件定義書 4.3）
# 画面（lib/types.ts）と項目名をそろえる。片方だけ変えないこと。

from typing import Literal

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    relationship: Literal["senior", "peer", "boss", "junior", "client"] = Field(description="相手との関係性")
    preference_knowledge: Literal["low", "mid", "high"] = Field(description="好みの把握度（low=ほとんど知らない）")
    total_budget: int = Field(gt=0, description="贈り手全員の合計予算（円）")
    num_givers: int = Field(default=1, ge=1, description="連名で贈る人数")
    handover: Literal["hand", "ship"] = Field(default="hand", description="渡し方（hand=職場で手渡し）")
    theme_ids: list[str] = Field(default_factory=list, description="エピソードから抽出したテーマ（来週。今は空）")
    limit: int = Field(default=3, ge=1, le=5, description="返す件数（3〜5）")


class Candidate(BaseModel):
    rank: int
    product_id: str
    product_name: str
    category: str
    brand: str | None = None
    price: int
    score: float
    reasons: list[str]
    caution: str | None = None


class RecommendationResponse(BaseModel):
    per_person_budget: int
    applied_exclusions: list[str]
    candidate_count: int
    episode_used: bool
    results: list[Candidate]
