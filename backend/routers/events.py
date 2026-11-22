# routers/events.py — 利用ログを記録する窓口（FR-9・DR-7）
# 画面から「どの利用（session_id）で、どんな操作をしたか」を受け取り、event_logs に1行足す。
# エピソードの原文や個人情報は受け取らない・保存しない（NFR-1・NFR-7。入力の形は schemas.py の EventRequest で絞る）。

from fastapi import APIRouter, HTTPException

from schemas import EventRequest, EventResponse

router = APIRouter(prefix="/api", tags=["events"])

# 値は %s に params で渡す（文字列に直接つなげない）。created_at は DB の DEFAULT（いまの日時）に任せる
INSERT_SQL = "INSERT INTO event_logs (session_id, event_type, share_id, product_id) VALUES (%s, %s, %s, %s)"


@router.post("/events", response_model=EventResponse)
def create_event(req: EventRequest):
    """操作を1件記録して、記録できたかを返す"""
    from database import execute  # テストでは差し替えるので、ここで読み込む（DB接続設定が無くてもテストできる）

    params = (
        str(req.session_id),
        req.event_type,
        str(req.share_id) if req.share_id else None,
        req.product_id,
    )
    try:
        execute(INSERT_SQL, params)
    except Exception:
        # 入力値はログにもエラー文にも出さない（将来項目が増えても漏れないように）
        raise HTTPException(status_code=503, detail="利用ログを記録できませんでした")
    return {"ok": True}
