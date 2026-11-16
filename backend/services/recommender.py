# services/recommender.py — 送別の候補を取り、外れにくさで並べる（FR-3・FR-4）
#
# 処理は3段に分けてある。
#   1. fetch_candidates   … 班のDBから候補を取る（SQL）。送別タグ・在庫あり・価格帯・属性あり
#   2. filter_candidates  … 状況に応じて「外れやすい商品」を除く（Python）
#   3. score_candidates   … 6つの要素×重みの合計で並べ、理由を付ける（Python）
# 2と3は商品のリストを受け取るだけの関数で、DBにつながなくてもテストできる（tests/test_recommender.py）。
# 順位付けに生成AIは使わない。同じ入力なら必ず同じ順位になる（要件定義書 6.1）。

import math

from services.reasons import build_reasons
from services.weights import weights_for

# 予算の基準は「総予算」。連名で1つの品を買う送別なので、総予算の70%〜100%を価格帯にする（要件定義書 6.2・6.4 No.1）
PRICE_FLOOR_RATIO = 0.7
# 食品で日持ちがこれ未満のものは、職場で渡してすぐ食べきれないので除く（要件定義書 6.2）
MIN_SHELF_LIFE_DAYS = 14
# 評価の補正に使う「事前のレビュー件数」。レビューが少ない商品の評価を、全体の平均に寄せる（ベイズ平均）
RATING_PRIOR_COUNT = 20
DEFAULT_LIMIT = 3
MAX_LIMIT = 5

# 属性の値 → 0〜1 の点（1が「外れにくい」）
PREFERENCE_POINTS = {"low": 1.0, "mid": 0.5, "high": 0.0}   # 好みへの依存度
SCENT_POINTS = {"none": 1.0, "weak": 0.5, "strong": 0.0}     # 香りの強さ


def price_band(total_budget: int) -> tuple[int, int]:
    """総予算から候補の価格帯（下限・上限）を出す。4,500円なら 3,150〜4,500円。"""
    return math.ceil(total_budget * PRICE_FLOOR_RATIO), total_budget


# ── 1. 候補の取得（DB） ─────────────────────────────────────
CANDIDATE_SQL = """
SELECT p.product_id, p.product_name, p.category, p.brand, p.price, p.rating, p.review_count, p.stock,
       a.preference_dependency, a.scent_level, a.room_temp_ok, a.individually_wrapped,
       a.shelf_life_days, a.carry_size, a.shareable, a.workplace_friendly, a.style,
       COALESCE(s.sobetsu_orders, 0) AS sobetsu_orders
FROM products p
JOIN product_attributes a ON a.product_id = p.product_id
LEFT JOIN (
    SELECT oi.product_id, COUNT(DISTINCT o.order_id) AS sobetsu_orders
    FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.estimated_scene = '送別'
      AND o.ordered_at >= (SELECT DATE_SUB(MAX(ordered_at), INTERVAL 1 YEAR) FROM orders)
    GROUP BY oi.product_id
) s ON s.product_id = p.product_id
WHERE EXISTS (SELECT 1 FROM product_scenes ps WHERE ps.product_id = p.product_id AND ps.scene_tag = '送別')
  AND p.stock > 0
  AND p.price BETWEEN %s AND %s
"""


def fetch_candidates(total_budget: int) -> list[dict]:
    """送別タグ付き・在庫あり・価格帯内・属性付与済みの商品を取る。送別での購入数（直近1年）も一緒に集計する。"""
    from database import fetch_all  # テストでは呼ばないので、ここで読み込む（DB接続設定が無くてもテストできる）
    low, high = price_band(total_budget)
    return fetch_all(CANDIDATE_SQL, (low, high))


# ── 2. 除外条件 ─────────────────────────────────────────
def filter_candidates(candidates: list[dict], cond: dict) -> tuple[list[dict], list[str]]:
    """状況に合わない商品を除き、残った商品と「適用した除外条件」の説明を返す。"""
    low, high = price_band(cond["total_budget"])
    rules = [(f"価格が{low:,}〜{high:,}円の範囲外", lambda p: not (low <= p["price"] <= high))]
    if cond["handover"] == "hand":
        rules += [
            ("職場で手渡し：要冷蔵の商品", lambda p: p.get("room_temp_ok") == 0),
            ("職場で手渡し：持ち帰りが負担になる大きさ", lambda p: p.get("carry_size") == "large"),
        ]
    if cond["preference_knowledge"] == "low":
        rules += [
            ("好みをほとんど知らない：好みへの依存度が高い商品", lambda p: p.get("preference_dependency") == "high"),
            ("好みをほとんど知らない：香りが強い商品", lambda p: p.get("scent_level") == "strong"),
        ]
    rules.append((f"食品：日持ちが{MIN_SHELF_LIFE_DAYS}日未満",
                  lambda p: p.get("shelf_life_days") is not None and p["shelf_life_days"] < MIN_SHELF_LIFE_DAYS))

    kept = [p for p in candidates if not any(hit(p) for _, hit in rules)]
    applied = [label for label, hit in rules if any(hit(p) for p in candidates)]
    return kept, applied


# ── 3. 順位付け ─────────────────────────────────────────
def factor_values(p: dict, cond: dict, ctx: dict) -> dict:
    """1商品の6要素を、それぞれ 0〜1 の点にする。1 が「その要素で見て外れにくい」。"""
    pref = PREFERENCE_POINTS.get(p.get("preference_dependency"), 0.5)
    scent = SCENT_POINTS.get(p.get("scent_level"), 0.5)

    themes = set(cond.get("theme_ids") or [])
    matched = themes & set(p.get("theme_ids") or [])
    episode = len(matched) / len(themes) if themes else 0.0      # FR-5（来週）。今週はテーマが無いので 0

    n = p.get("sobetsu_orders") or 0
    sales = math.log1p(n) / math.log1p(ctx["max_sales"]) if ctx["max_sales"] > 0 else 0.0

    rc, r = p.get("review_count") or 0, float(p.get("rating") or 0)
    bayes = (rc * r + RATING_PRIOR_COUNT * ctx["mean_rating"]) / (rc + RATING_PRIOR_COUNT)

    style_point = {"low": {"standard": 1.0, "unique": 0.0},
                   "mid": {"standard": 0.5, "unique": 0.5},
                   "high": {"standard": 0.0, "unique": 1.0}}[cond["preference_knowledge"]]

    return {
        "preference": (pref + scent) / 2,
        "episode": episode,
        "workplace": float(p.get("workplace_friendly") or 0),
        "sales": sales,
        "rating": bayes / 5,
        "style": style_point.get(p.get("style"), 0.5),
    }


def score_candidates(candidates: list[dict], cond: dict) -> list[dict]:
    """6要素×重みの合計（0〜1）で並べ、候補ごとに理由2つ・注意点1つを付けて返す。"""
    if not candidates:
        return []
    weights = weights_for(cond["preference_knowledge"], cond["handover"])
    rated = [float(p.get("rating") or 0) for p in candidates if p.get("review_count")]
    ctx = {
        "max_sales": max(p.get("sobetsu_orders") or 0 for p in candidates),
        "mean_rating": sum(rated) / len(rated) if rated else 4.0,
    }
    scored = []
    for p in candidates:
        values = factor_values(p, cond, ctx)
        contrib = {k: weights[k] * v for k, v in values.items()}
        reasons, caution = build_reasons(p, values, contrib)
        scored.append({**p, "score": round(sum(contrib.values()), 4), "contributions": contrib,
                       "reasons": reasons, "caution": caution})
    # 同点なら、送別での購入数が多い方 → 商品IDの順（毎回同じ順位にするため）
    scored.sort(key=lambda x: (-x["score"], -(x.get("sobetsu_orders") or 0), x["product_id"]))
    return scored


def recommend(cond: dict, fetch=fetch_candidates) -> dict:
    """FR-3・FR-4・FR-6 をまとめて実行する。fetch を差し替えると、DBなしで動かせる（テスト用）。"""
    limit = min(max(int(cond.get("limit") or DEFAULT_LIMIT), 1), MAX_LIMIT)
    candidates = fetch(cond["total_budget"])
    kept, applied = filter_candidates(candidates, cond)
    ranked = score_candidates(kept, cond)
    return {
        "per_person_budget": cond["total_budget"] // max(cond["num_givers"], 1),
        "applied_exclusions": applied,
        "candidate_count": len(kept),
        "episode_used": bool(cond.get("theme_ids")),
        "results": ranked[:limit],
    }
