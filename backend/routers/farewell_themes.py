# /api/farewell/themes（FR-2 エピソードからのテーマ抽出）
# 抽出の処理は services/theme_extractor.py に任せ、ここは「受け取る・返す」だけにする。
# 原文は保存しない（NFR-1）。受け取りは POST の本文にして、URL（アクセスログに残る）には載せない。

from fastapi import APIRouter

from schemas import ThemeRequest, ThemeResponse
from services.theme_extractor import extract_themes

router = APIRouter(prefix="/api/farewell", tags=["farewell"])


@router.post("/themes", response_model=ThemeResponse)
def themes(req: ThemeRequest):
    """エピソードの文章から相手の手がかりを読み取り、テーマID（最大3件）で返す"""
    return extract_themes(req.episode)
