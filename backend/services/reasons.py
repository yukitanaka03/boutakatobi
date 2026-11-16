# services/reasons.py — 選定理由と注意点を作る（FR-6）
#
# スコアへの効き（重み×点）が大きい要素の上位2つを理由にし、気をつける点があれば1つ添える（要件定義書 6.3）。
# 文言は定型文（sql/seed/reason_templates.csv）から選ぶ。生成AIで毎回書かせると、同じ商品でも理由がぶれるため。
# データに根拠の無い理由は出さない：点が THRESHOLD 未満の要素は、効きが大きくても理由にしない。

import csv
from functools import lru_cache
from pathlib import Path

TEMPLATE_CSV = Path(__file__).resolve().parent.parent / "sql" / "seed" / "reason_templates.csv"
THRESHOLD = 0.5   # この点以上の要素だけを理由にする


@lru_cache(maxsize=1)
def load_templates() -> dict:
    """(target_type, target_key, target_value) → 表示する文言 の辞書。"""
    with open(TEMPLATE_CSV, encoding="utf-8") as f:
        return {(r["target_type"], r["target_key"], r["target_value"]): r["text"] for r in csv.DictReader(f)}


def _text(target_type: str, key: str, value) -> str | None:
    return load_templates().get((target_type, key, str(value)))


def reason_for(factor: str, p: dict) -> str | None:
    """要素ごとに、商品の属性値から定型文を選ぶ。"""
    if factor == "preference":
        # 香りなし を優先し、無ければ好みへの依存度で言う
        # 「好みに左右されにくい」と言うのは、依存度が low と分かっている商品だけ（属性と矛盾させないため）
        if p.get("scent_level") == "none" and p.get("preference_dependency") == "low":
            return _text("attribute", "scent_level", "none")
        return _text("attribute", "preference_dependency", p.get("preference_dependency"))
    if factor == "workplace":
        return _text("attribute", "workplace_friendly", 1)
    if factor == "sales":
        t = _text("attribute", "sobetsu_orders", "any")
        return t.format(n=p.get("sobetsu_orders") or 0) if t else None
    if factor == "rating":
        # レビューが無い商品は、評価を理由にしない（「評価None（0件）」と表示されるのを防ぐ）
        if not p.get("review_count") or p.get("rating") is None:
            return None
        t = _text("attribute", "rating", "any")
        return t.format(r=p.get("rating"), n=p.get("review_count") or 0) if t else None
    if factor == "style":
        return _text("attribute", "style", p.get("style"))
    return None   # episode は来週（テーマの文言は target_type=theme で足す）


def caution_for(p: dict) -> str | None:
    """気をつける点を1つだけ選ぶ。上から順に、当てはまった最初のもの。"""
    checks = [
        (p.get("preference_dependency") == "mid" and p.get("shelf_life_days") is not None, "food_taste"),
        (p.get("scent_level") == "weak", "scent_weak"),
        (p.get("shelf_life_days") is not None and p["shelf_life_days"] < 30, "short_shelf_life"),
        (p.get("carry_size") == "medium", "carry_medium"),
    ]
    for hit, key in checks:
        if hit:
            t = _text("caution", key, "any")
            return t.format(days=p.get("shelf_life_days")) if t else None
    return None


def build_reasons(p: dict, values: dict, contrib: dict) -> tuple[list[str], str | None]:
    """理由（最大2つ）と注意点（最大1つ）を返す。"""
    order = sorted((k for k in contrib if contrib[k] > 0 and values[k] >= THRESHOLD),
                   key=lambda k: -contrib[k])
    reasons = []
    for factor in order:
        text = reason_for(factor, p)
        if text and text not in reasons:
            reasons.append(text)
        if len(reasons) == 2:
            break
    if not reasons:
        # どの要素も理由にできなかった候補にも、必ず1つは理由を出す（FR-6）。
        # 候補はすべて「送別タグ付き・予算内」で取っている（FR-3）ので、どの候補にも当てはまる事実を使う
        fallback = _text("attribute", "scene_budget", "any")
        if fallback:
            reasons.append(fallback)
    return reasons, caution_for(p)
