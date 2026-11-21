# tests/test_fr5.py — FR-5（エピソードとの関連度）のテスト
#
# 要件定義書 3章の確認方法「同じ条件で、エピソードの有無によって順位が意図どおりに変わるか」と、
# 6.4 No.2〜4 の期待結果を、架空の商品で確かめる。班のDBにはつながない。
# 実行：backend フォルダで  python -m unittest discover -s tests -t . -v

import csv
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from services import recommender
from services.reasons import load_templates, theme_names
from services.recommender import fetch_candidates, recommend
from tests.test_recommender import NO1, fake_fetch, item

SEED_DIR = Path(__file__).resolve().parent.parent / "sql" / "seed"
COFFEE, SWEETS, OUTDOOR, DESK = "T001", "T004", "T006", "T009"

# 6.4 No.1〜3 用（3,150〜4,500円）。タオルはテーマなしで、外れにくさだけなら1位になる
P = [
    item("F01", "国産タオルギフトセット", 4400, rating=4.7, review_count=120, sobetsu_orders=104),
    item("F02", "ドリップバッグ アソート", 3300, category="飲料", preference_dependency="mid",
         shelf_life_days=180, sobetsu_orders=55, theme_ids=[COFFEE], theme_confidence={COFFEE: 0.9}),
    item("F03", "コーヒーに合う焼き菓子", 3780, category="食品", preference_dependency="mid", individually_wrapped=1,
         shelf_life_days=60, sobetsu_orders=40, theme_ids=[COFFEE, SWEETS], theme_confidence={COFFEE: 0.7, SWEETS: 0.9}),
    item("F04", "銘柄限定のコーヒー豆", 4000, category="飲料", preference_dependency="high",
         shelf_life_days=90, theme_ids=[COFFEE], theme_confidence={COFFEE: 0.9}),
    item("F05", "ショコラアソート", 3400, category="食品", preference_dependency="mid", individually_wrapped=1,
         shelf_life_days=60, sobetsu_orders=150, theme_ids=[SWEETS], theme_confidence={SWEETS: 0.9}),
    item("F06", "ボタニカルハンドクリーム 金木犀", 3300, category="コスメ", preference_dependency="high",
         scent_level="strong", theme_ids=[DESK], theme_confidence={DESK: 0.7}),
]


def rank_of(out, pid):
    ids = [r["product_id"] for r in out["results"]]
    return ids.index(pid) + 1 if pid in ids else None


class TestFR5Episode(unittest.TestCase):
    def test_エピソードがあるとテーマの合う商品の順位が上がる(self):
        before = recommend(dict(NO1, limit=5), fetch=fake_fetch(P))
        after = recommend(dict(NO1, limit=5, theme_ids=[COFFEE]), fetch=fake_fetch(P))
        self.assertFalse(before["episode_used"])
        self.assertTrue(after["episode_used"])
        self.assertEqual(rank_of(before, "F01"), 1)                         # エピソードなしはタオルが1位
        self.assertEqual(rank_of(after, "F02"), 1)                          # 6.4 No.2：コーヒーが1位に上がる
        self.assertLess(rank_of(after, "F03"), rank_of(before, "F03"))

    def test_好みをほとんど知らないなら依存度が高いコーヒー商品は出さない(self):
        out = recommend(dict(NO1, limit=5, theme_ids=[COFFEE]), fetch=fake_fetch(P))
        self.assertIsNone(rank_of(out, "F04"))                              # 6.4 No.2「来てはいけない」
        self.assertIsNone(rank_of(out, "F06"))                              # 香りの強い商品も出ない

    def test_少し知っているなら甘いもののテーマで焼き菓子が上位に来る(self):
        out = recommend(dict(NO1, preference_knowledge="mid", limit=5, theme_ids=[SWEETS]), fetch=fake_fetch(P))
        self.assertEqual({r["product_id"] for r in out["results"][:2]}, {"F03", "F05"})   # 6.4 No.3

    def test_テーマに合う商品が無ければエピソードなしと同じ順位で返し通知する(self):
        before = recommend(dict(NO1, limit=5), fetch=fake_fetch(P))
        out = recommend(dict(NO1, limit=5, theme_ids=[OUTDOOR]), fetch=fake_fetch(P))
        self.assertFalse(out["episode_used"])                               # 画面で「反映できなかった」と出す
        self.assertEqual([r["product_id"] for r in out["results"]], [r["product_id"] for r in before["results"]])

    def test_テーマが複数でも合う商品の点は薄まらない(self):
        one = recommend(dict(NO1, limit=5, theme_ids=[COFFEE]), fetch=fake_fetch(P))
        many = recommend(dict(NO1, limit=5, theme_ids=[COFFEE, DESK, "T016"]), fetch=fake_fetch(P))
        self.assertEqual(rank_of(many, "F02"), 1)                           # 「マグカップでコーヒー」の例文
        self.assertEqual(one["results"][0]["score"], many["results"][0]["score"])

    def test_確からしさが高いテーマの方が点が高い(self):
        out = recommend(dict(NO1, limit=5, theme_ids=[COFFEE]), fetch=fake_fetch(P))
        by = {r["product_id"]: r for r in out["results"]}
        self.assertAlmostEqual(by["F02"]["contributions"]["episode"], 0.25 * 0.9)   # 商品名で付いたテーマ
        self.assertAlmostEqual(by["F03"]["contributions"]["episode"], 0.25 * 0.7)   # 説明文だけで付いたテーマ

    def test_テーマが合った商品にはテーマの理由と合ったテーマ名が付く(self):
        out = recommend(dict(NO1, limit=5, theme_ids=[COFFEE]), fetch=fake_fetch(P))
        by = {r["product_id"]: r for r in out["results"]}
        self.assertIn("コーヒー好きの方に", by["F02"]["reasons"])
        self.assertEqual(by["F02"]["matched_themes"], ["コーヒー"])
        self.assertEqual(by["F01"]["matched_themes"], [])                    # テーマなしの商品には付けない
        self.assertNotIn("コーヒー好きの方に", by["F01"]["reasons"])

    def test_テーマの理由はエピソードで先に出たテーマを使う(self):
        out = recommend(dict(NO1, preference_knowledge="mid", limit=5, theme_ids=[SWEETS, COFFEE]), fetch=fake_fetch(P))
        f03 = next(r for r in out["results"] if r["product_id"] == "F03")
        self.assertIn("甘いもの好きの方に", f03["reasons"])
        self.assertEqual(f03["matched_themes"], ["甘いもの", "コーヒー"])


class TestFR5Fetch(unittest.TestCase):
    def test_候補のSQLで商品のテーマも取る(self):
        sql = recommender.CANDIDATE_SQL
        self.assertIn("LEFT JOIN", sql)                                     # テーマの無い商品も候補に残す
        self.assertIn("FROM product_themes", sql)
        self.assertIn("COALESCE(confidence, 1)", sql)                       # manual（NULL）は確かなものとして 1

    def test_まとめたテーマを商品ごとのIDと確からしさに戻す(self):
        fake_db = types.ModuleType("database")
        fake_db.fetch_all = lambda sql, params=(): [
            dict(item("F02", "ドリップ", 3300), themes="T001:0.90,T009:1"),
            dict(item("F01", "タオル", 4400), themes=None),
        ]
        with mock.patch.dict(sys.modules, {"database": fake_db}):
            rows = fetch_candidates(4500)
        by = {r["product_id"]: r for r in rows}
        self.assertEqual(by["F02"]["theme_ids"], [COFFEE, DESK])
        self.assertEqual(by["F02"]["theme_confidence"], {COFFEE: 0.9, DESK: 1.0})
        self.assertEqual((by["F01"]["theme_ids"], by["F01"]["theme_confidence"]), ([], {}))
        self.assertNotIn("themes", by["F02"])                               # 画面に返す形に余計な列を残さない


class TestThemeSeeds(unittest.TestCase):
    """sql/seed の語彙・商品とテーマ・理由文が、要件定義書 5.2 どおりで互いに食い違っていないか"""

    def setUp(self):
        with open(SEED_DIR / "product_themes.csv", encoding="utf-8") as f:
            self.links = list(csv.DictReader(f))
        with open(SEED_DIR / "product_attributes.csv", encoding="utf-8") as f:
            self.attr_ids = {r["product_id"] for r in csv.DictReader(f)}

    def test_語彙は20から30語でIDの形がそろっている(self):
        names = theme_names()
        self.assertTrue(20 <= len(names) <= 30)                              # DR-2
        for theme_id in names:
            self.assertRegex(theme_id, r"^T\d{3}$")

    def test_どのテーマにも理由文がある(self):
        keys = {k for (t, k, _) in load_templates() if t == "theme"}
        self.assertEqual(keys, set(theme_names()))

    def test_商品とテーマの対応は語彙と属性付与済みの商品だけを使い重複しない(self):
        pairs = [(r["product_id"], r["theme_id"]) for r in self.links]
        self.assertEqual(len(pairs), len(set(pairs)))
        for r in self.links:
            self.assertIn(r["theme_id"], theme_names(), msg=r)
            self.assertIn(r["product_id"], self.attr_ids, msg=r)              # 候補に出ない商品にテーマを付けない
            self.assertIn(r["source"], ("ai", "manual"), msg=r)
            if r["source"] == "ai":
                self.assertTrue(0 <= float(r["confidence"]) <= 1, msg=r)

    def test_どのテーマにも商品が3件以上ある(self):
        counts = {t: 0 for t in theme_names()}
        for r in self.links:
            counts[r["theme_id"]] += 1
        self.assertEqual([t for t, n in counts.items() if n < 3], [])        # 5.3 未確認②「一致する商品が十分あるか」


if __name__ == "__main__":
    unittest.main()
