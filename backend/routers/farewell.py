# routers/farewell.py — 送別の候補を返す窓口（FR-3・FR-4・FR-6）
# 計算は services/recommender.py に任せ、ここは「受け取る・返す」だけにする。
# /api/farewell/themes（FR-2 エピソードからのテーマ抽出）は来週足す。

from fastapi import APIRouter

from schemas import Candidate, RecommendationRequest, RecommendationResponse
from services.recommender import recommend

router = APIRouter(prefix="/api/farewell", tags=["farewell"])


@router.post("/recommendations", response_model=RecommendationResponse)
def recommendations(req: RecommendationRequest):
    """送別の状況を受け取り、外れにくい順に候補と理由を返す"""
    out = recommend(req.model_dump())
    out["results"] = [
        Candidate(rank=i + 1, **{k: r.get(k) for k in Candidate.model_fields if k != "rank"})
        for i, r in enumerate(out["results"])
    ]
    return out
