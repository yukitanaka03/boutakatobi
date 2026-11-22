# services/shares.py — 共有ページの保存と読み出し（FR-7・DR-5・DR-6）
#
# 共有を発行するときは、画面から受け取った入力条件で候補をサーバー側で計算し直し、
# share_lists に1行（DR-5）＋候補ごとに share_list_items に1行（DR-6）を、まとめて保存する。
# 理由文は共有した時点のものを固定して保存する（後で商品属性が変わっても、共有ページの表示を変えないため）。
# エピソードの原文・個人情報は保存しない（NFR-1・NFR-7）。テーマは theme_id だけ。
# SQL の組み立てと詰め替えは DB なしで動く関数に分けてある（recommender.py と同じ流儀。テストしやすくするため）。

import uuid

from services.recommender import recommend

SHARE_DAYS = 30  # 閲覧期限（発行から30日。NFR）
SCENE_TAG = "送別"  # 今は送別だけ

# 値は %s に params で渡す（文字列に直接つなげない）。
# 発行日時（DEFAULT）と閲覧期限は、どちらも DB の時計にそろえる（PC と DB で時刻がずれないように）
INSERT_SHARE_SQL = (
    "INSERT INTO share_lists (share_id, expires_at, scene_tag, relationship, preference_knowledge, "
    "total_budget, num_givers, handover, theme_ids) "
    "VALUES (%s, DATE_ADD(NOW(), INTERVAL %s DAY), %s, %s, %s, %s, %s, %s, %s)"
)
# rank は MySQL 8 の予約語なのでバッククォートで囲む
INSERT_ITEM_SQL = (
    "INSERT INTO share_list_items (share_id, `rank`, product_id, score, reason_text) VALUES (%s, %s, %s, %s, %s)"
)
# 期限切れかどうかも DB の時計で判定して一緒に返す（expired が 1 なら期限切れ）
SELECT_SHARE_SQL = (
    "SELECT share_id, created_at, expires_at, relationship, preference_knowledge, total_budget, num_givers, "
    "handover, expires_at < NOW() AS expired FROM share_lists WHERE share_id = %s"
)
# 商品名・価格などは products から。理由文は共有時点で保存した reason_text を使う
SELECT_ITEMS_SQL = (
    "SELECT i.`rank`, i.product_id, p.product_name, p.category, p.brand, p.price, i.score, i.reason_text "
    "FROM share_list_items i JOIN products p ON p.product_id = i.product_id "
    "WHERE i.share_id = %s ORDER BY i.`rank`"
)


class NoCandidatesError(ValueError):
    """共有できる候補が0件のとき（ルーターで 400 にする）"""


def build_insert_statements(share_id: str, cond: dict, results: list[dict]) -> list[tuple[str, tuple]]:
    """保存する SQL と値の並びを作る。share_lists に1行＋候補ごとに1行（rank は1から）。
    注意点（caution）は保存しない（共有ページの表示項目 4.2 に無いため）。"""
    theme_ids = cond.get("theme_ids") or []
    statements = [(
        INSERT_SHARE_SQL,
        (
            share_id,
            SHARE_DAYS,
            SCENE_TAG,
            cond["relationship"],
            cond["preference_knowledge"],
            cond["total_budget"],
            cond["num_givers"],
            cond["handover"],
            ",".join(theme_ids) if theme_ids else None,  # 入力なしは NULL
        ),
    )]
    for i, r in enumerate(results, start=1):
        reason_text = "\n".join(r.get("reasons") or [])  # 複数の理由は改行でつないで1つの文に
        statements.append((INSERT_ITEM_SQL, (share_id, i, r["product_id"], r["score"], reason_text)))
    return statements


def to_share_response(share_row: dict, item_rows: list[dict]) -> dict:
    """DB の行を、共有ページの形（schemas.py の ShareResponse）に詰め替える"""
    return {
        "share_id": share_row["share_id"],
        "created_at": share_row["created_at"],
        "expires_at": share_row["expires_at"],
        "relationship": share_row["relationship"],
        "preference_knowledge": share_row["preference_knowledge"],
        "total_budget": share_row["total_budget"],
        "num_givers": share_row["num_givers"],
        "per_person_budget": share_row["total_budget"] // max(share_row["num_givers"], 1),
        "handover": share_row["handover"],
        "items": [
            {
                "rank": r["rank"],
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "category": r["category"],
                "brand": r["brand"],
                "price": r["price"],
                "score": float(r["score"]),  # DB の DECIMAL を JSON で扱える小数に
                # 改行で分けて理由の箇条書きに戻す（空行は除く）
                "reasons": [t for t in (r["reason_text"] or "").split("\n") if t.strip()],
            }
            for r in item_rows
        ],
    }


def create_share(cond: dict, recommend_fn=recommend, run=None, fetch=None) -> dict:
    """候補を計算し直して保存し、共有ID・URLのパス・閲覧期限を返す。
    recommend_fn・run・fetch を差し替えると DB なしで動かせる（テスト用）。"""
    results = recommend_fn(cond)["results"]
    if not results:
        raise NoCandidatesError("共有できる候補がありません")

    if run is None or fetch is None:
        from database import execute_in_transaction, fetch_all  # DB接続設定が無くてもテストできるよう、ここで読み込む
        run = run or execute_in_transaction
        fetch = fetch or fetch_all

    share_id = str(uuid.uuid4())  # 推測されにくい ID（NFR）
    run(build_insert_statements(share_id, cond, results))
    # 閲覧期限は DB が決めた値を読み直して返す（共有ページで表示する期限と同じ値になるように）
    expires_at = fetch(SELECT_SHARE_SQL, (share_id,))[0]["expires_at"]
    return {"share_id": share_id, "share_path": f"/share/{share_id}", "expires_at": expires_at}


def get_share(share_id: str, fetch=None) -> tuple[str, dict | None]:
    """共有ページの中身を読む。("ok", 中身) / ("not_found", None) / ("expired", None) のどれかを返す。"""
    if fetch is None:
        from database import fetch_all  # DB接続設定が無くてもテストできるよう、ここで読み込む
        fetch = fetch_all

    rows = fetch(SELECT_SHARE_SQL, (share_id,))
    if not rows:
        return "not_found", None
    if rows[0]["expired"]:
        return "expired", None
    items = fetch(SELECT_ITEMS_SQL, (share_id,))
    return "ok", to_share_response(rows[0], items)
