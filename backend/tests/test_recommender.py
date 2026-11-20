# tests/test_recommender.py — 候補の除外と順位付けのテスト（要件定義書 6.4）
#
# 班のDBにはつながない。架空の商品データ（下の P）を fetch の代わりに渡して、ロジックだけを確かめる。
# 実行：backend フォルダで  python -m unittest discover -s tests -v

import unittest

from services.recommender import filter_candidates, price_band, recommend, score_candidates
from services.weights import NO_EPISODE, WITH_EPISODE, weights_for


def item(pid, name, price, **attrs):
    base = dict(product_id=pid, product_name=name, category="生活雑貨", brand="", price=price,
                rating=4.3, review_count=100, stock=10,
                preference_dependency="low", scent_level="none", room_temp_ok=1,
                individually_wrapped=None, shelf_life_days=None, carry_size="small",
                shareable=0, workplace_friendly=1, style="standard", sobetsu_orders=50)
    base.update(attrs)
    return base


# 6.4 No.1 用（総予算4,500円 → 3,150〜4,500円）
P = [
    item("T01", "Lino 国産タオルギフトセット", 4400, rating=4.7, review_count=120, sobetsu_orders=104),
    item("T02", "ボタニカルハンドクリーム 金木犀", 3300, category="コスメ", preference_dependency="high",
         scent_level="strong", rating=4.4, review_count=387, sobetsu_orders=811),
    item("T03", "焼き菓子アソート 15個入", 3980, category="食品", preference_dependency="mid",
         individually_wrapped=1, shelf_life_days=60, rating=4.5, review_count=558, sobetsu_orders=355),
    item("T04", "生チーズケーキ", 4000, category="食品", room_temp_ok=0, workplace_friendly=0, shelf_life_days=5),
    item("T05", "ミニタオル", 2500),                      # 予算の7割未満
    item("T06", "名入れボールペン", 5000),                # 予算超え
    item("T07", "生どら焼き", 3600, category="食品", shelf_life_days=7),
    item("T08", "ドリップバッグ アソート", 3500, category="飲料", preference_dependency="mid",
         scent_level="weak", shelf_life_days=180, sobetsu_orders=266),
]

NO1 = dict(relationship="senior", preference_knowledge="low", total_budget=4500, num_givers=3, handover="hand")


def fake_fetch(products):
    return lambda total_budget: [dict(p) for p in products]


class TestWeights(unittest.TestCase):
    def test_どの条件でも重みの合計は1(self):
        for k, w in WITH_EPISODE.items():
            self.assertAlmostEqual(sum(w.values()), 1.0, msg=k)
        self.assertAlmostEqual(sum(NO_EPISODE.values()), 1.0)
        for k in WITH_EPISODE:
            for h in ("hand", "ship"):
                for e in (True, False):
                    self.assertAlmostEqual(sum(weights_for(k, h, e).values()), 1.0, msg=f"{k}/{h}/{e}")

    def test_エピソードなしは把握度に関係なく共通の重み(self):
        self.assertEqual(weights_for("low", "hand"), weights_for("high", "hand"))
        self.assertEqual(weights_for("low", "hand")["unique"], 0.0)

    def test_配送なら渡しやすさの重みを好みに左右されにくさに足す(self):
        hand, ship = weights_for("low", "hand"), weights_for("low", "ship")
        self.assertEqual(ship["workplace"], 0.0)
        self.assertAlmostEqual(ship["preference"], hand["preference"] + hand["workplace"])


class TestNo1(unittest.TestCase):
    """先輩・好みはほとんど知らない・総予算4,500円・3人・職場で手渡し・エピソードなし"""

    def setUp(self):
        self.out = recommend(NO1, fetch=fake_fetch(P))
        self.ids = [r["product_id"] for r in self.out["results"]]

    def test_価格帯は総予算の7割から総予算まで(self):
        self.assertEqual(price_band(4500), (3150, 4500))
        for r in self.out["results"]:
            self.assertTrue(3150 <= r["price"] <= 4500, r["product_name"])

    def test_来てはいけない商品が出ない(self):
        # 香りの強いハンドクリーム（Aさんが香りで見送った）、要冷蔵、日持ち14日未満、予算外
        for bad in ("T02", "T04", "T05", "T06", "T07"):
            self.assertNotIn(bad, self.ids)

    def test_好みに左右されにくく職場で渡しやすい商品が1位(self):
        self.assertEqual(self.ids[0], "T01")

    def test_送別の購入数が最多でも香りが強ければ出ない(self):
        # 実績だけで並べると1位になる商品（送別811件）が、除外で消えること
        self.assertNotIn("T02", self.ids)

    def test_除外した条件を画面に出せる(self):
        applied = " ".join(self.out["applied_exclusions"])
        for word in ("要冷蔵", "香りが強い", "日持ち", "範囲外"):
            self.assertIn(word, applied)

    def test_理由は1つ以上2つまでで属性と矛盾しない(self):
        for r in self.out["results"]:
            self.assertTrue(1 <= len(r["reasons"]) <= 2, r["product_name"])
        top = self.out["results"][0]
        self.assertIn("香りなし・好みに左右されにくい", top["reasons"])

    def test_注意点は当てはまる商品にだけ付く(self):
        by_id = {r["product_id"]: r for r in self.out["results"]}
        self.assertEqual(by_id["T03"]["caution"], "味の好みは要確認")
        self.assertIsNone(by_id["T01"]["caution"])

    def test_1人あたりの予算(self):
        self.assertEqual(self.out["per_person_budget"], 1500)

    def test_同じ入力なら同じ順位(self):
        again = recommend(NO1, fetch=fake_fetch(P))
        self.assertEqual(self.ids, [r["product_id"] for r in again["results"]])


class TestNo5(unittest.TestCase):
    """上司・好みはほとんど知らない・総予算15,000円・5人・職場で手渡し・エピソードなし"""

    def test_予算に対して安すぎる商品と大きすぎる商品が出ない(self):
        products = [
            item("U01", "本革名刺入れ", 11400, category="ビジネス小物", sobetsu_orders=218),
            item("U02", "観葉植物 大鉢", 12000, carry_size="large", workplace_friendly=0),
            item("U03", "タオルセット", 8000),
            item("U04", "カタログギフト", 15000, category="カタログギフト"),
        ]
        cond = dict(NO1, relationship="boss", total_budget=15000, num_givers=5)
        ids = [r["product_id"] for r in recommend(cond, fetch=fake_fetch(products))["results"]]
        self.assertNotIn("U02", ids)   # 持ち帰りが負担
        self.assertNotIn("U03", ids)   # 10,500円未満
        self.assertEqual(set(ids), {"U01", "U04"})


class TestKnowledge(unittest.TestCase):
    def test_エピソードがあり好みをよく知っていれば個性的な商品が上に来る(self):
        a = item("S01", "定番の品", 4000, style="standard")
        b = item("S02", "個性的な品", 4000, style="unique")
        low = score_candidates([a, b], dict(NO1, preference_knowledge="low", theme_ids=["T001"]))
        high = score_candidates([a, b], dict(NO1, preference_knowledge="high", theme_ids=["T001"]))
        self.assertEqual(low[0]["product_id"], "S01")
        self.assertEqual(high[0]["product_id"], "S02")

    def test_エピソードがなければ好みをよく知っていても定番が上(self):
        # 好みの中身が入力されていないので、個性的な商品を上に出す根拠が無い（要件定義書 6.2）
        a = item("S01", "定番の品", 4000, style="standard")
        b = item("S02", "個性的な品", 4000, style="unique")
        high = score_candidates([a, b], dict(NO1, preference_knowledge="high"))
        self.assertEqual(high[0]["product_id"], "S01")

    def test_好みを少しでも知っていれば依存度が高い商品も候補に残る(self):
        kept, _ = filter_candidates(P, dict(NO1, preference_knowledge="mid"))
        self.assertIn("T02", [p["product_id"] for p in kept])

    def test_候補が0件でも落ちない(self):
        out = recommend(NO1, fetch=fake_fetch([]))
        self.assertEqual(out["results"], [])
        self.assertEqual(out["candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()


class TestRealDataFindings(unittest.TestCase):
    """実データ（送別上位163商品）で流して見つかった問題の再発防止"""

    def test_同じカテゴリーは2件までで残りは別カテゴリーから(self):
        towels = [item(f"W{i}", f"タオル{i}", 4000, sobetsu_orders=100 - i) for i in range(5)]
        sweets = [item("F1", "焼き菓子", 4000, category="食品", preference_dependency="mid",
                       shelf_life_days=60, individually_wrapped=1, sobetsu_orders=10)]
        out = recommend(dict(NO1, limit=3), fetch=fake_fetch(towels + sweets))
        cats = [r["category"] for r in out["results"]]
        self.assertEqual(cats.count("生活雑貨"), 2)
        self.assertIn("食品", cats)

    def test_候補が1カテゴリーしか無ければそのカテゴリーで埋める(self):
        towels = [item(f"W{i}", f"タオル{i}", 4000) for i in range(5)]
        out = recommend(dict(NO1, limit=3), fetch=fake_fetch(towels))
        self.assertEqual(len(out["results"]), 3)

    def test_配送なら持ち帰りの注意は出ない(self):
        bath = item("B1", "バスタオルセット", 4000, carry_size="medium")
        hand = recommend(NO1, fetch=fake_fetch([bath]))["results"][0]
        ship = recommend(dict(NO1, handover="ship"), fetch=fake_fetch([bath]))["results"][0]
        self.assertEqual(hand["caution"], "持ち帰りに紙袋が必要な大きさ")
        self.assertIsNone(ship["caution"])

    def test_味の好みに注意がある商品に好みの理由を出さない(self):
        sweets = item("F1", "焼き菓子", 4000, category="食品", preference_dependency="mid",
                      shelf_life_days=60, individually_wrapped=1)
        r = recommend(dict(NO1, preference_knowledge="mid"), fetch=fake_fetch([sweets]))["results"][0]
        self.assertEqual(r["caution"], "味の好みは要確認")
        self.assertNotIn("好みが分かれにくい", r["reasons"])
        self.assertTrue(all("好み" not in t for t in r["reasons"]))

    def test_食品と飲料には香りなしを理由にしない(self):
        coffee = item("D1", "ドリップバッグ", 3500, category="飲料", preference_dependency="mid", shelf_life_days=180)
        r = recommend(NO1, fetch=fake_fetch([coffee]))["results"][0]
        self.assertTrue(all("香り" not in t for t in r["reasons"]))
