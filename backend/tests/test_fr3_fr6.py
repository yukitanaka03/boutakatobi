# tests/test_fr3_fr6.py — FR-3（候補の取得）と FR-6（選定理由の表示）のテスト
#
# 要件定義書 3章の「確認方法」をそのままテストにしている。
#   FR-3：取得した商品がすべて送別タグ付き・予算内であるか
#   FR-6：表示されたすべての候補に理由が表示され、商品の属性と矛盾しないか
# 班のDBにはつながない。DBを呼ぶ部分は偽物（fake）に差し替えて、渡すSQLと値だけを確かめる。
# 実行：backend フォルダで  python -m unittest discover -s tests -t . -v

import csv
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from services import recommender
from services.reasons import load_templates
from services.recommender import fetch_candidates, price_band, recommend, score_candidates
from tests.test_recommender import NO1, fake_fetch, item

SEED_DIR = Path(__file__).resolve().parent.parent / "sql" / "seed"


# ── FR-3 候補の取得 ─────────────────────────────────────
class TestFR3Fetch(unittest.TestCase):
    def test_SQLに送別タグと在庫と属性付与済みの条件がある(self):
        sql = recommender.CANDIDATE_SQL
        self.assertIn("ps.scene_tag = '送別'", sql)            # 送別タグ付き
        self.assertIn("p.stock > 0", sql)                      # 在庫あり
        self.assertIn("JOIN product_attributes a", sql)        # 属性が付与済みの商品だけ
        self.assertIn("p.price BETWEEN %s AND %s", sql)        # 価格は %s で渡す（文字列連結しない）

    def test_価格帯の下限と上限を値として渡している(self):
        calls = []
        fake_db = types.ModuleType("database")
        fake_db.fetch_all = lambda sql, params=(): calls.append((sql, params)) or []
        with mock.patch.dict(sys.modules, {"database": fake_db}):
            self.assertEqual(fetch_candidates(4500), [])
        self.assertEqual(calls, [(recommender.CANDIDATE_SQL, (3150, 4500))])

    def test_価格帯は総予算の7割以上で総予算以下(self):
        self.assertEqual(price_band(15000), (10500, 15000))   # 6.4 No.5
        self.assertEqual(price_band(1), (1, 1))               # 端数は切り上げ（7割未満を含めない）
        self.assertEqual(price_band(10), (7, 10))
        self.assertEqual(price_band(4999), (3500, 4999))      # 3499.3 → 切り上げて 3500
        for budget in range(1, 20001):
            low, high = price_band(budget)
            self.assertEqual(high, budget)
            self.assertGreaterEqual(low * 10, budget * 7)       # 下限は7割以上
            self.assertLess((low - 1) * 10, budget * 7)         # それより1円安いと7割未満

    def test_予算の境界ちょうどの商品は含み1円でも外れたら含まない(self):
        products = [item("B1", "下限ちょうど", 3150), item("B2", "上限ちょうど", 4500),
                    item("B3", "下限より1円安い", 3149), item("B4", "上限より1円高い", 4501)]
        out = recommend(dict(NO1, limit=5), fetch=fake_fetch(products))
        self.assertEqual({r["product_id"] for r in out["results"]}, {"B1", "B2"})


# ── FR-6 選定理由の表示 ─────────────────────────────────
# 理由を付けにくい商品（レビューなし・実績なし・好みへの依存度が高い など）をわざと混ぜる
HARD = [
    item("H1", "レビューも実績もない個性的な品", 4000, rating=None, review_count=0, sobetsu_orders=0,
         preference_dependency="high", workplace_friendly=0, style="unique"),
    item("H2", "評価が低く香りが強い品", 4000, rating=2.0, review_count=500, sobetsu_orders=0,
         preference_dependency="high", scent_level="strong", workplace_friendly=0),
    item("H3", "香りはないが好みが分かれる品", 4000, preference_dependency="high", sobetsu_orders=0),
    item("H4", "ふつうの定番品", 4000),
]


def all_conditions():
    for knowledge in ("low", "mid", "high"):
        for handover in ("hand", "ship"):
            yield dict(NO1, preference_knowledge=knowledge, handover=handover)


class TestFR6Reasons(unittest.TestCase):
    def test_どの条件でもすべての候補に理由が1つ以上2つまで付く(self):
        for cond in all_conditions():
            for r in score_candidates(HARD, cond):
                label = f'{cond["preference_knowledge"]}/{cond["handover"]}/{r["product_id"]}'
                self.assertTrue(1 <= len(r["reasons"]) <= 2, label)
                self.assertTrue(all(r["reasons"]), label)   # 空文字や None が混ざらない

    def test_ほかに理由がない候補には送別向けで予算内と表示する(self):
        r = score_candidates([HARD[1]], dict(NO1, preference_knowledge="high", handover="ship"))[0]
        self.assertEqual(r["reasons"], ["送別向けで予算内の品"])

    def test_理由は商品の属性と矛盾しない(self):
        for cond in all_conditions():
            for r in score_candidates(HARD, cond):
                text = " ".join(r["reasons"])
                if r["preference_dependency"] == "high":
                    self.assertNotIn("好みに左右されにくい", text, r["product_id"])
                if r["scent_level"] != "none":
                    self.assertNotIn("香りなし", text, r["product_id"])
                if not r["workplace_friendly"] or cond["handover"] == "ship":
                    self.assertNotIn("職場で渡しやすい", text, r["product_id"])
                if not r["review_count"]:
                    self.assertNotIn("評価", text, r["product_id"])
                if not r["sobetsu_orders"]:
                    self.assertNotIn("送別で選ばれている", text, r["product_id"])
                if r["style"] != "standard":
                    self.assertNotIn("定番", text, r["product_id"])
                self.assertNotIn("None", text, r["product_id"])   # 値が無いまま文に埋め込まれていない
                self.assertNotIn("{", text, r["product_id"])      # 置き換え前の記号が残っていない

    def test_好みに左右されにくいと言うのは依存度がlowの商品だけ(self):
        for dep in ("mid", "high", None, "HIGH"):   # None や書き間違いの値でも言わない
            p = item("D1", "香りなしの品", 4000, preference_dependency=dep)
            for cond in all_conditions():
                text = " ".join(score_candidates([p], cond)[0]["reasons"])
                self.assertNotIn("好みに左右されにくい", text, f"{dep}")

    def test_評価がDecimal型でも落ちない(self):
        # 班のDBは DECIMAL の列を Decimal 型で返す
        from decimal import Decimal
        p = item("D2", "x", Decimal("4000"), rating=Decimal("4.5"))
        out = recommend(NO1, fetch=fake_fetch([p]))
        self.assertEqual(len(out["results"]), 1)

    def test_理由文の定型文は30字以内(self):
        # 要件定義書 5.2 reason_templates.text。{n} などは実際の値に置き換わるので、長めの値で数える
        # テーマの理由文の {関係性} は、いちばん長い「取引先の方」で数える
        for key, text in load_templates().items():
            shown = text.format(n=9999, r=4.5, days=180, **{"関係性": "取引先の方"})
            self.assertLessEqual(len(shown), 30, key)


# ── 手付与の属性データ（sql/seed/product_attributes.csv）の書き間違いチェック ──
ALLOWED = {
    "preference_dependency": {"low", "mid", "high"},
    "scent_level": {"none", "weak", "strong"},
    "room_temp_ok": {"0", "1"},
    "individually_wrapped": {"0", "1", ""},     # 空欄＝食品以外（NULL）
    "carry_size": {"small", "medium", "large"},
    "shareable": {"0", "1"},
    "workplace_friendly": {"0", "1"},
    "style": {"standard", "unique"},
    "source": {"ai", "manual"},
}


class TestSeedProductAttributes(unittest.TestCase):
    """行が0件（見出しだけ）でも通る。行を足したら、DBに入れる前にここで書き間違いを見つける。"""

    def setUp(self):
        with open(SEED_DIR / "product_attributes.csv", encoding="utf-8-sig") as f:
            self.rows = list(csv.DictReader(f))

    def test_取りうる値だけが入っている(self):
        for row in self.rows:
            for col, allowed in ALLOWED.items():
                self.assertIn(row[col], allowed, f'{row["product_id"]} の {col}')
            if row["shelf_life_days"]:
                self.assertGreaterEqual(int(row["shelf_life_days"]), 0, row["product_id"])

    def test_商品IDが重複していない(self):
        ids = [row["product_id"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_職場で渡しやすいかはルールどおり(self):
        # 要件定義書 5.2：常温で保存でき、大きさが large 以外で、香りが強くないものを 1 とする
        for row in self.rows:
            expected = "1" if (row["room_temp_ok"] == "1" and row["carry_size"] != "large"
                               and row["scent_level"] != "strong") else "0"
            self.assertEqual(row["workplace_friendly"], expected, row["product_id"])


if __name__ == "__main__":
    unittest.main()
