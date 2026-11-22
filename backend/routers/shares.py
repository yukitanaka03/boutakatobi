# routers/shares.py — 共有ページの窓口（FR-7・DR-5・DR-6）
# 保存・読み出しの中身は services/shares.py に任せ、ここは「受け取る・返す・エラーを分ける」だけにする。
# 共有ページはログインなしで誰でも見られる。URL の share_id は推測されにくい UUID、閲覧期限は発行から30日（NFR）。
# エピソードの原文や個人情報は受け取らない・保存しない（NFR-1・NFR-7）。

from uuid import UUID

from fastapi import APIRouter, HTTPException

from schemas import RecommendationRequest, ShareCreateResponse, ShareResponse
from services import shares as share_service

router = APIRouter(prefix="/api/shares", tags=["shares"])


@router.post("", response_model=ShareCreateResponse)
def create_share(req: RecommendationRequest):
    """入力条件を受け取り、候補を計算し直して保存し、共有ページのパスと閲覧期限を返す"""
    try:
        return share_service.create_share(req.model_dump())
    except share_service.NoCandidatesError:
        raise HTTPException(status_code=400, detail="共有できる候補がありません")
    except Exception:
        # 入力値はログにもエラー文にも出さない（events.py と同じ）
        raise HTTPException(status_code=503, detail="共有ページを作成できませんでした")


@router.get("/{share_id}", response_model=ShareResponse)
def read_share(share_id: UUID):
    """共有ページの中身を返す。UUID の形でない ID は FastAPI が 422 にする"""
    try:
        status, data = share_service.get_share(str(share_id))
    except Exception:
        raise HTTPException(status_code=503, detail="共有ページを読み込めませんでした")
    if status == "not_found":
        raise HTTPException(status_code=404, detail="共有ページが見つかりません")
    if status == "expired":
        raise HTTPException(status_code=410, detail="閲覧期限が過ぎました")
    return data
