# schemas.py — /api/farewell/recommendations の入力と出力の形（要件定義書 4.3）
# 画面（lib/types.ts）と項目名をそろえる。片方だけ変えないこと。

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


# ── /api/events（利用ログ FR-9・DR-7）の入力と出力 ──────────────
# 操作の種類は6つだけ。画面（lib/events.ts の EventType）と並び・綴りをそろえる。
EventType = Literal["input_submit", "episode_submit", "results_view", "share_create", "share_view", "product_click"]


class EventRequest(BaseModel):
    # 決めた項目以外を受け付けない（エピソード原文や氏名が混ざって保存されるのを防ぐ NFR-1・NFR-7）
    model_config = ConfigDict(extra="forbid")

    session_id: UUID = Field(description="利用の単位（画面が初回アクセス時に発行する UUID）")
    event_type: EventType = Field(description="操作の種類")
    share_id: UUID | None = Field(default=None, description="関連する共有ページの UUID（共有の発行・閲覧のとき）")
    product_id: str | None = Field(
        default=None, pattern=r"^G\d{4,8}$", max_length=10, description="関連する商品ID（例 G0001。商品ページへ移動のとき）"
    )

    @model_validator(mode="after")
    def check_required_ids(self):
        """共有の操作には共有ID、商品ページへの移動には商品IDが要る（足りなければ 422 になる）"""
        if self.event_type in ("share_create", "share_view") and self.share_id is None:
            raise ValueError(f"{self.event_type} には share_id が必要です")
        if self.event_type == "product_click" and self.product_id is None:
            raise ValueError("product_click には product_id が必要です")
        return self


class EventResponse(BaseModel):
    ok: bool  # 記録できたか


# ── /api/shares（共有ページ FR-7・DR-5・DR-6）の入力と出力 ──────────────
# 発行の入力は RecommendationRequest をそのまま使う（新しい型は作らない）。
# サーバー側で候補を計算し直して保存する。画面から理由文は受け取らない
# （ログインなしで誰でも見られるページなので、書き換えた文言を保存させないため）。


class ShareCreateResponse(BaseModel):
    share_id: str
    # "/share/{share_id}"。API は画面の URL（オリジン）を知らないので、画面側で window.location.origin とつなげる
    share_path: str
    expires_at: datetime  # 閲覧期限（発行から30日）


class ShareItem(BaseModel):
    rank: int
    product_id: str
    product_name: str
    category: str
    brand: str | None = None
    price: int
    score: float
    reasons: list[str]  # 共有した時点の理由文（後で商品属性が変わっても変わらない DR-6）


class ShareResponse(BaseModel):
    # relationship・preference_knowledge・handover は RecommendationRequest と同じ値だけ（片方だけ変えないこと）
    share_id: str
    created_at: datetime
    expires_at: datetime
    relationship: Literal["senior", "peer", "boss", "junior", "client"]
    preference_knowledge: Literal["low", "mid", "high"]
    total_budget: int
    num_givers: int
    per_person_budget: int
    handover: Literal["hand", "ship"]
    items: list[ShareItem]
