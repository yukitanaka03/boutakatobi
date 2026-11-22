# tests/test_fr7_shares.py — FR-7（共有ページの発行）と DR-5・DR-6（共有の保存）のテスト
#
# 要件定義書の「確認方法」をそのままテストにしている。
#   FR-7：共有ページの URL を発行し、ログインなしで閲覧できる（共有IDは推測されにくい UUID、閲覧期限は発行から30日）
#   DR-5：共有を発行するたびに1行が登録されるか
#   DR-6：共有後に商品属性を変えても、共有ページの表示が変わらないか（保存した理由文を返し、計算し直さない）
#   NFR-1・NFR-7：エピソード原文・個人情報を保存しない
#   AGENTS.md：SQL の値は %s プレースホルダ＋params で渡す
# 班のDBにはつながない。DBを呼ぶ部分は偽物（fake）に差し替えて、渡すSQLと値だけを確かめる。
# 実行：backend フォルダで  python -m unittest discover -s tests -t . -v

import importlib
import re
import sys
import types
import typing
import unittest
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from routers import shares as share_router
from schemas import RecommendationRequest, ShareCreateResponse, ShareItem, ShareResponse
from services import shares
from services.recommender import recommend
from tests.test_recommender import NO1, fake_fetch, item

BACKEND_DIR = Path(__file__).resolve().parent.parent
DDL_003 = BACKEND_DIR / "sql" / "003_create_share_tables.sql"
DDL_002 = BACKEND_DIR / "sql" / "002_create_event_logs.sql"
FRONT_TYPES_TS = BACKEND_DIR.parent / "giftia-frontend" / "lib" / "types.ts"

EXPIRES = datetime(2026, 12, 21, 10, 0, 0)
CREATED = datetime(2026, 11, 21, 10, 0, 0)

# 候補計算の結果の代わり（recommend の results と同じ形）
RESULTS = [
    {"rank": 1, "product_id": "G0001", "product_name": "タオル", "category": "生活雑貨", "brand": "Lino",
     "price": 4400, "score": 0.8123, "reasons": ["定番で外れにくい", "職場で手渡ししやすい"], "caution": "注意A"},
    {"rank": 2, "product_id": "G0002", "product_name": "焼き菓子", "category": "食品", "brand": None,
     "price": 3980, "score": 0.7, "reasons": ["個包装で配りやすい"], "caution": None},
    {"rank": 3, "product_id": "G0003", "product_name": "コーヒー", "category": "飲料", "brand": "",
     "price": 3500, "score": 0.5, "reasons": [], "caution": "香りあり"},
]

# 画面から届く入力条件（RecommendationRequest.model_dump() と同じ形）
COND = dict(NO1, theme_ids=[], limit=3)


def fixed_recommend(results):
    return lambda cond: {"results": [dict(r) for r in results]}


def recorder():
    """run（execute_in_transaction の代わり）と fetch（fetch_all の代わり）を記録する偽物"""
    runs, fetches = [], []

    def run(statements):
        runs.append(statements)

    def fetch(sql, params=()):
        fetches.append((sql, params))
        return [{"expires_at": EXPIRES}]

    return run, fetch, runs, fetches


def share_row(**over):
    row = dict(share_id=str(uuid.uuid4()), created_at=CREATED, expires_at=EXPIRES, relationship="senior",
               preference_knowledge="low", total_budget=4500, num_givers=3, handover="hand", expired=0)
    row.update(over)
    return row


def item_rows():
    return [
        dict(rank=1, product_id="G0001", product_name="タオル", category="生活雑貨", brand="Lino", price=4400,
             score=Decimal("0.8123"), reason_text="定番で外れにくい\n職場で手渡ししやすい"),
        dict(rank=2, product_id="G0002", product_name="焼き菓子", category="食品", brand=None, price=3980,
             score=Decimal("0.7000"), reason_text="個包装で配りやすい\n\n  \n"),
    ]


def stored_fetch(srow, irows, calls=None):
    """保存済みの行を返す偽 fetch（SQL の種類で返す行を変える）"""
    def fetch(sql, params=()):
        if calls is not None:
            calls.append((sql, params))
        if sql == shares.SELECT_SHARE_SQL:
            return [dict(srow)] if srow else []
        if sql == shares.SELECT_ITEMS_SQL:
            return [dict(r) for r in irows]
        raise AssertionError(f"想定外の SQL: {sql}")
    return fetch


def must_not_recommend(cond):
    raise AssertionError("共有ページの閲覧で recommend を呼び直してはいけない（DR-6）")


def active_sql_lines(text):
    """SQL ファイルからコメント（-- 以降）を除いた、実際に実行される部分だけを返す"""
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def fake_database(products, fail_run=False):
    """ルーターを通しで動かすための偽 database モジュール（候補の取得・保存・読み直し）"""
    db = types.ModuleType("database")
    db.runs = []

    def fetch_all(sql, params=()):
        if sql == shares.SELECT_SHARE_SQL:
            return [{"expires_at": EXPIRES}]
        return [dict(p) for p in products]  # 候補の取得（CANDIDATE_SQL）

    def execute_in_transaction(statements):
        if fail_run:
            raise RuntimeError("接続できません")
        db.runs.append(statements)

    db.fetch_all = fetch_all
    db.execute_in_transaction = execute_in_transaction
    return db


# ── DR-5 発行するたびに1行 ─────────────────────────────────
class TestDR5OneRowPerShare(unittest.TestCase):
    def test_1回の発行でshare_listsに1行と候補数ぶんの行をまとめて1回で保存する(self):
        run, fetch, runs, _ = recorder()
        shares.create_share(COND, recommend_fn=fixed_recommend(RESULTS), run=run, fetch=fetch)
        self.assertEqual(len(runs), 1)                                       # トランザクションは1回
        statements = runs[0]
        sqls = [s for s, _ in statements]
        self.assertEqual(sqls.count(shares.INSERT_SHARE_SQL), 1)             # share_lists はちょうど1行（DR-5）
        self.assertEqual(sqls[0], shares.INSERT_SHARE_SQL)                   # 見出しが先（外部キーのため）
        self.assertEqual(sqls.count(shares.INSERT_ITEM_SQL), len(RESULTS))   # 候補ごとに1行（DR-6）
        self.assertEqual(len(statements), 1 + len(RESULTS))

    def test_2回発行すると別々のUUIDバージョン4の共有IDになる(self):
        run, fetch, runs, _ = recorder()
        a = shares.create_share(COND, recommend_fn=fixed_recommend(RESULTS), run=run, fetch=fetch)
        b = shares.create_share(COND, recommend_fn=fixed_recommend(RESULTS), run=run, fetch=fetch)
        self.assertEqual(len(runs), 2)                                       # 発行するたびに保存される
        self.assertNotEqual(a["share_id"], b["share_id"])
        for out in (a, b):
            u = uuid.UUID(out["share_id"])
            self.assertEqual(u.version, 4)                                   # 乱数の UUID（推測されにくい）
            self.assertEqual(str(u), out["share_id"])                        # 36文字の標準形
            self.assertEqual(len(out["share_id"]), 36)                       # CHAR(36) に入る
        self.assertEqual(runs[0][0][1][0], a["share_id"])                    # 保存した ID と返した ID が同じ
        self.assertEqual(runs[1][0][1][0], b["share_id"])

    def test_同じshare_idが全部の行に入る(self):
        run, fetch, runs, _ = recorder()
        out = shares.create_share(COND, recommend_fn=fixed_recommend(RESULTS), run=run, fetch=fetch)
        for _, params in runs[0]:
            self.assertEqual(params[0], out["share_id"])


# ── 保存する値 ─────────────────────────────────────────
class TestFR7SavedValues(unittest.TestCase):
    def test_share_listsに期限30日_送別_入力条件が入る(self):
        sid = str(uuid.uuid4())
        sql, params = shares.build_insert_statements(sid, COND, RESULTS)[0]
        self.assertEqual(shares.SHARE_DAYS, 30)
        self.assertEqual(shares.SCENE_TAG, "送別")
        self.assertEqual(params, (sid, 30, "送別", "senior", "low", 4500, 3, "hand", None))

    def test_テーマは空ならNone_複数ならカンマ区切り(self):
        sid = str(uuid.uuid4())
        get = lambda cond: shares.build_insert_statements(sid, cond, RESULTS)[0][1][-1]
        self.assertIsNone(get(dict(COND, theme_ids=[])))
        self.assertIsNone(get({k: v for k, v in COND.items() if k != "theme_ids"}))  # 項目なしも NULL
        self.assertIsNone(get(dict(COND, theme_ids=None)))
        self.assertEqual(get(dict(COND, theme_ids=["T001"])), "T001")
        self.assertEqual(get(dict(COND, theme_ids=["T001", "T002"])), "T001,T002")

    def test_候補はrank1から連番_scoreそのまま_理由は改行つなぎ_注意点は保存しない(self):
        sid = str(uuid.uuid4())
        items = shares.build_insert_statements(sid, COND, RESULTS)[1:]
        self.assertEqual([p for _, p in items], [
            (sid, 1, "G0001", 0.8123, "定番で外れにくい\n職場で手渡ししやすい"),
            (sid, 2, "G0002", 0.7, "個包装で配りやすい"),
            (sid, 3, "G0003", 0.5, ""),                                       # 理由なしは空文字（NOT NULL に入る）
        ])
        flat = [v for _, p in items for v in p]
        for caution in ("注意A", "香りあり"):
            self.assertNotIn(caution, flat)                                  # caution は保存されない

    def test_rankは結果の並び順で振り直す(self):
        shuffled = [dict(RESULTS[1], rank=9), dict(RESULTS[0], rank=7)]
        items = shares.build_insert_statements("x", COND, shuffled)[1:]
        self.assertEqual([(p[1], p[2]) for _, p in items], [(1, "G0002"), (2, "G0001")])

    def test_エピソード原文や氏名は保存する値に含まれない(self):
        # 画面がうっかり余分な項目を送っても、RecommendationRequest で落ち、保存値には入らない（NFR-1・NFR-7）
        req = RecommendationRequest(**NO1, episode="送別会で泣いてくれた先輩", name="山田太郎",
                                    email="taro@example.com")
        cond = req.model_dump()
        self.assertNotIn("episode", cond)
        self.assertNotIn("name", cond)
        flat = [v for _, p in shares.build_insert_statements("x", cond, RESULTS) for v in p]
        for secret in ("送別会で泣いてくれた先輩", "山田太郎", "taro@example.com"):
            self.assertNotIn(secret, flat)


# ── 発行の戻り値 ───────────────────────────────────────
class TestFR7CreateReturn(unittest.TestCase):
    def test_共有IDとパスと読み直した期限を返す(self):
        run, fetch, runs, fetches = recorder()
        out = shares.create_share(COND, recommend_fn=fixed_recommend(RESULTS), run=run, fetch=fetch)
        self.assertEqual(set(out), {"share_id", "share_path", "expires_at"})
        self.assertEqual(out["share_path"], f"/share/{out['share_id']}")
        self.assertEqual(out["expires_at"], EXPIRES)                         # DB から読み直した値
        self.assertEqual(fetches, [(shares.SELECT_SHARE_SQL, (out["share_id"],))])
        ShareCreateResponse(**out)                                           # response_model の形に合う

    def test_入力条件をそのまま候補計算に渡す(self):
        seen = []
        run, fetch, _, _ = recorder()

        def rec(cond):
            seen.append(cond)
            return {"results": RESULTS}

        shares.create_share(COND, recommend_fn=rec, run=run, fetch=fetch)
        self.assertEqual(seen, [COND])

    def test_本物のrecommendで計算した結果をそのまま保存する(self):
        products = [item("G0101", "タオル", 4400), item("G0102", "焼き菓子", 3980, category="食品"),
                    item("G0103", "ハンカチ", 3500, category="服飾")]
        expected = recommend(COND, fetch=fake_fetch(products))["results"]
        run, fetch, runs, _ = recorder()
        shares.create_share(COND, recommend_fn=lambda c: recommend(c, fetch=fake_fetch(products)),
                            run=run, fetch=fetch)
        saved = [p for _, p in runs[0][1:]]
        self.assertEqual([p[2] for p in saved], [r["product_id"] for r in expected])
        self.assertEqual([p[3] for p in saved], [r["score"] for r in expected])
        self.assertEqual([p[4] for p in saved], ["\n".join(r["reasons"]) for r in expected])


# ── 候補0件 ──────────────────────────────────────────
class TestFR7NoCandidates(unittest.TestCase):
    def test_0件ならNoCandidatesErrorでDBに何も書かない(self):
        run, fetch, runs, fetches = recorder()
        with self.assertRaises(shares.NoCandidatesError):
            shares.create_share(COND, recommend_fn=fixed_recommend([]), run=run, fetch=fetch)
        self.assertEqual(runs, [])
        self.assertEqual(fetches, [])

    def test_ルーターでは400になりDBに何も書かない(self):
        db = fake_database(products=[])                                      # 候補が1件もない
        with mock.patch.dict(sys.modules, {"database": db}):
            with self.assertRaises(HTTPException) as cm:
                share_router.create_share(RecommendationRequest(**NO1))
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(db.runs, [])


# ── DR-6 保存した理由文を返す（計算し直さない） ─────────────────
class TestDR6Snapshot(unittest.TestCase):
    def test_閲覧時は保存済みの理由文を返しrecommendを呼ばない(self):
        srow = share_row()
        with mock.patch.object(shares, "recommend", must_not_recommend), \
             mock.patch("services.recommender.recommend", must_not_recommend), \
             mock.patch("services.recommender.fetch_candidates", must_not_recommend):
            status, data = shares.get_share(srow["share_id"], fetch=stored_fetch(srow, item_rows()))
        self.assertEqual(status, "ok")
        self.assertEqual(data["items"][0]["reasons"], ["定番で外れにくい", "職場で手渡ししやすい"])

    def test_商品属性が変わって計算結果が変わっても同じ保存行からは同じ表示になる(self):
        # 発行時：G0001 が1位の結果を保存する
        run, fetch, runs, _ = recorder()
        before = [item("G0001", "タオル", 4400, rating=4.9, sobetsu_orders=900),
                  item("G0002", "焼き菓子", 3980, category="食品", rating=3.0, sobetsu_orders=1)]
        cond = dict(COND, limit=3)
        shares.create_share(cond, recommend_fn=lambda c: recommend(c, fetch=fake_fetch(before)), run=run, fetch=fetch)
        saved_items = runs[0][1:]
        srow = share_row(share_id=runs[0][0][1][0])
        irows = [dict(rank=p[1], product_id=p[2], product_name={"G0001": "タオル", "G0002": "焼き菓子"}[p[2]],
                      category="生活雑貨", brand="", price=4000, score=Decimal(str(p[3])), reason_text=p[4])
                 for _, p in saved_items]
        first = shares.get_share(srow["share_id"], fetch=stored_fetch(srow, irows))

        # 発行後に属性が変わった想定（G0001 の評価が下がり、香りが強くなった）。いま計算し直すと結果が変わる
        after = [item("G0001", "タオル", 4400, rating=2.0, review_count=500, scent_level="strong",
                      preference_dependency="high", sobetsu_orders=0),
                 item("G0002", "焼き菓子", 3980, category="食品", rating=4.9, sobetsu_orders=900)]
        now = recommend(cond, fetch=fake_fetch(after))["results"]
        then = recommend(cond, fetch=fake_fetch(before))["results"]
        self.assertNotEqual([(r["product_id"], r["reasons"]) for r in now],
                            [(r["product_id"], r["reasons"]) for r in then])  # 計算結果は本当に変わっている

        with mock.patch.object(shares, "recommend", must_not_recommend):
            second = shares.get_share(srow["share_id"], fetch=stored_fetch(srow, irows))
        self.assertEqual(first, second)                                      # 共有ページの表示は変わらない（DR-6）
        self.assertEqual([i["reasons"] for i in second[1]["items"]], [r["reasons"] for r in then])

    def test_理由文の空行は除かれる(self):
        srow = share_row()
        _, data = shares.get_share(srow["share_id"], fetch=stored_fetch(srow, item_rows()))
        self.assertEqual(data["items"][1]["reasons"], ["個包装で配りやすい"])
        empty = [dict(item_rows()[0], reason_text="")]
        _, data = shares.get_share(srow["share_id"], fetch=stored_fetch(srow, empty))
        self.assertEqual(data["items"][0]["reasons"], [])
        none = [dict(item_rows()[0], reason_text=None)]
        _, data = shares.get_share(srow["share_id"], fetch=stored_fetch(srow, none))
        self.assertEqual(data["items"][0]["reasons"], [])

    def test_1人あたり予算は合計を人数で割った切り捨て_scoreはfloat(self):
        srow = share_row(total_budget=10000, num_givers=3)
        _, data = shares.get_share(srow["share_id"], fetch=stored_fetch(srow, item_rows()))
        self.assertEqual(data["per_person_budget"], 3333)
        for i in data["items"]:
            self.assertIs(type(i["score"]), float)
        self.assertEqual(data["items"][0]["score"], 0.8123)

    def test_詰め替えで保存行の値がそのまま入る(self):
        srow = share_row()
        _, data = shares.get_share(srow["share_id"], fetch=stored_fetch(srow, item_rows()))
        for k in ("share_id", "created_at", "expires_at", "relationship", "preference_knowledge",
                  "total_budget", "num_givers", "handover"):
            self.assertEqual(data[k], srow[k], k)
        self.assertNotIn("expired", data)
        self.assertEqual([(i["rank"], i["product_id"], i["brand"]) for i in data["items"]],
                         [(1, "G0001", "Lino"), (2, "G0002", None)])


# ── 閲覧（get_share とルーター） ─────────────────────────────
class TestFR7Read(unittest.TestCase):
    def test_行がなければnot_found(self):
        calls = []
        sid = str(uuid.uuid4())
        self.assertEqual(shares.get_share(sid, fetch=stored_fetch(None, [], calls)), ("not_found", None))
        self.assertEqual(calls, [(shares.SELECT_SHARE_SQL, (sid,))])

    def test_期限切れならexpiredで候補を取りに行かない(self):
        calls = []
        srow = share_row(expired=1)
        self.assertEqual(shares.get_share(srow["share_id"], fetch=stored_fetch(srow, item_rows(), calls)),
                         ("expired", None))
        self.assertEqual([s for s, _ in calls], [shares.SELECT_SHARE_SQL])

    def test_正常ならokとShareResponseとして検証できる中身(self):
        calls = []
        srow = share_row()
        status, data = shares.get_share(srow["share_id"], fetch=stored_fetch(srow, item_rows(), calls))
        self.assertEqual(status, "ok")
        self.assertEqual(calls, [(shares.SELECT_SHARE_SQL, (srow["share_id"],)),
                                 (shares.SELECT_ITEMS_SQL, (srow["share_id"],))])
        model = ShareResponse(**data)
        self.assertEqual(len(model.items), 2)
        self.assertIsInstance(model.items[0], ShareItem)

    def test_ルーターは見つからなければ404_期限切れは410_例外は503(self):
        sid = uuid.uuid4()
        cases = [(("not_found", None), 404), (("expired", None), 410)]
        for ret, code in cases:
            with mock.patch.object(share_router.share_service, "get_share", return_value=ret):
                with self.assertRaises(HTTPException) as cm:
                    share_router.read_share(sid)
            self.assertEqual(cm.exception.status_code, code)

        with mock.patch.object(share_router.share_service, "get_share", side_effect=RuntimeError("接続できません")):
            with self.assertRaises(HTTPException) as cm:
                share_router.read_share(sid)
        self.assertEqual(cm.exception.status_code, 503)
        self.assertNotIn("接続できません", str(cm.exception.detail))
        self.assertNotIn(str(sid), str(cm.exception.detail))

    def test_ルーターは正常なら中身を返しIDは文字列で渡す(self):
        sid = uuid.uuid4()
        srow = share_row(share_id=str(sid))
        data = shares.to_share_response(srow, item_rows())
        with mock.patch.object(share_router.share_service, "get_share", return_value=("ok", data)) as m:
            out = share_router.read_share(sid)
        m.assert_called_once_with(str(sid))
        self.assertEqual(out, data)
        ShareResponse(**out)

    def test_ルーターを偽DBで通しで動かしても閲覧でrecommendを呼ばない(self):
        srow = share_row()
        db = types.ModuleType("database")
        db.fetch_all = stored_fetch(srow, item_rows())
        with mock.patch.dict(sys.modules, {"database": db}), \
             mock.patch("services.recommender.fetch_candidates", must_not_recommend):
            out = share_router.read_share(uuid.UUID(srow["share_id"]))
        self.assertEqual(ShareResponse(**out).share_id, srow["share_id"])


# ── ルーターの発行 ─────────────────────────────────────
class TestFR7CreateRouter(unittest.TestCase):
    def test_偽DBで通しで発行でき_1行と候補の行を保存する(self):
        products = [item("G0101", "タオル", 4400), item("G0102", "焼き菓子", 3980, category="食品"),
                    item("G0103", "ハンカチ", 3500, category="服飾")]
        db = fake_database(products)
        with mock.patch.dict(sys.modules, {"database": db}):
            out = share_router.create_share(RecommendationRequest(**NO1))
        self.assertEqual(len(db.runs), 1)
        sqls = [s for s, _ in db.runs[0]]
        self.assertEqual(sqls.count(shares.INSERT_SHARE_SQL), 1)
        self.assertGreaterEqual(sqls.count(shares.INSERT_ITEM_SQL), 1)
        model = ShareCreateResponse(**out)
        self.assertEqual(model.share_path, f"/share/{model.share_id}")
        self.assertEqual(model.expires_at, EXPIRES)

    def test_予期しない例外は503で入力値をエラー文に出さない(self):
        products = [item("G0101", "タオル", 4400)]
        req = RecommendationRequest(relationship="client", preference_knowledge="high", total_budget=4567,
                                    num_givers=7, handover="ship", theme_ids=["T0099"])
        with mock.patch.dict(sys.modules, {"database": fake_database(products, fail_run=True)}):
            with self.assertRaises(HTTPException) as cm:
                share_router.create_share(req)
        self.assertEqual(cm.exception.status_code, 503)
        detail = str(cm.exception.detail)
        for v in ("client", "4567", "T0099", "ship", "接続できません"):
            self.assertNotIn(v, detail)

    def test_サービスが例外を投げても503(self):
        with mock.patch.object(share_router.share_service, "create_share", side_effect=KeyError("x")):
            with self.assertRaises(HTTPException) as cm:
                share_router.create_share(RecommendationRequest(**NO1))
        self.assertEqual(cm.exception.status_code, 503)

    def test_入力条件をそのままサービスに渡す(self):
        req = RecommendationRequest(**NO1, theme_ids=["T001"], limit=5)
        ret = {"share_id": "x", "share_path": "/share/x", "expires_at": EXPIRES}
        with mock.patch.object(share_router.share_service, "create_share", return_value=ret) as m:
            self.assertEqual(share_router.create_share(req), ret)
        m.assert_called_once_with(req.model_dump())

    def test_閲覧のshare_idはUUID型で受け取る(self):
        hints = typing.get_type_hints(share_router.read_share)
        self.assertIs(hints["share_id"], uuid.UUID)                          # UUID の形でなければ 422


# ── SQL の値はプレースホルダで渡す（AGENTS.md） ─────────────────
class TestFR7SQL(unittest.TestCase):
    ALL = ("INSERT_SHARE_SQL", "INSERT_ITEM_SQL", "SELECT_SHARE_SQL", "SELECT_ITEMS_SQL")

    def test_4本とも_s_を使い値を埋め込んでいない(self):
        for name in self.ALL:
            sql = getattr(shares, name)
            self.assertIn("%s", sql, name)
            self.assertNotIn("{", sql, name)                                 # f文字列・format の跡がない
            self.assertNotIn("'", sql, name)                                 # 値を引用符で埋め込んでいない
            self.assertNotIn('"', sql, name)

    def test_s_の数とparamsの長さが一致する(self):
        sts = shares.build_insert_statements(str(uuid.uuid4()), COND, RESULTS)
        self.assertEqual(shares.INSERT_SHARE_SQL.count("%s"), len(sts[0][1]))
        self.assertEqual(shares.INSERT_SHARE_SQL.count("%s"), 9)
        for _, params in sts[1:]:
            self.assertEqual(shares.INSERT_ITEM_SQL.count("%s"), len(params))
        self.assertEqual(shares.SELECT_SHARE_SQL.count("%s"), 1)
        self.assertEqual(shares.SELECT_ITEMS_SQL.count("%s"), 1)
        for _, params in sts:
            self.assertIsInstance(params, tuple)

    def test_列の並びとparamsの並びが合う(self):
        cols = re.search(r"share_lists \((.*?)\) VALUES", shares.INSERT_SHARE_SQL).group(1)
        self.assertEqual([c.strip() for c in cols.split(",")],
                         ["share_id", "expires_at", "scene_tag", "relationship", "preference_knowledge",
                          "total_budget", "num_givers", "handover", "theme_ids"])
        cols = re.search(r"share_list_items \((.*?)\) VALUES", shares.INSERT_ITEM_SQL).group(1)
        self.assertEqual([c.strip() for c in cols.split(",")], ["share_id", "`rank`", "product_id", "score", "reason_text"])

    def test_期限はDBの時計で30日後_期限切れもDBの時計で判定(self):
        self.assertIn("DATE_ADD(NOW(), INTERVAL %s DAY)", shares.INSERT_SHARE_SQL)
        self.assertIn("expires_at < NOW()", shares.SELECT_SHARE_SQL)
        self.assertIn("AS expired", shares.SELECT_SHARE_SQL)
        self.assertIn("WHERE share_id = %s", shares.SELECT_SHARE_SQL)

    def test_候補は保存した理由文をrank順で読む(self):
        sql = shares.SELECT_ITEMS_SQL
        self.assertIn("i.reason_text", sql)                                  # 理由は share_list_items から
        self.assertIn("FROM share_list_items i", sql)
        self.assertNotIn("p.reason", sql)
        self.assertIn("WHERE i.share_id = %s", sql)
        self.assertRegex(sql, r"ORDER BY i\.`rank`\s*$")
        self.assertIn("`rank`", shares.INSERT_ITEM_SQL)                      # 予約語はバッククォート

    def test_SQLは入力で変わらない(self):
        sid = str(uuid.uuid4())
        sts = shares.build_insert_statements(sid, dict(COND, theme_ids=["T001'; DROP TABLE x; --"]), RESULTS)
        self.assertIs(sts[0][0], shares.INSERT_SHARE_SQL)
        for sql, _ in sts:
            self.assertNotIn(sid, sql)
            self.assertNotIn("DROP", sql)


# ── まとめて保存（execute_in_transaction） ─────────────────────
class FakeCursor:
    def __init__(self, log, fail_at=None):
        self.log, self.fail_at = log, fail_at

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, query, params=()):
        self.log.append(("execute", query, params))
        if self.fail_at is not None and len([x for x in self.log if x[0] == "execute"]) == self.fail_at:
            raise RuntimeError("2つ目で失敗")
        return 1


class FakeConn:
    def __init__(self, fail_at=None):
        self.log = []
        self.fail_at = fail_at

    def cursor(self):
        return FakeCursor(self.log, self.fail_at)

    def commit(self):
        self.log.append(("commit",))

    def rollback(self):
        self.log.append(("rollback",))

    def close(self):
        self.log.append(("close",))


class TestExecuteInTransaction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 本物の database.py を読み込む。.env は読ませない（load_dotenv を空にする）。DB にはつながない
        saved = sys.modules.pop("database", None)
        try:
            with mock.patch("dotenv.load_dotenv", lambda *a, **k: False):
                cls.db = importlib.import_module("database")
        finally:
            sys.modules.pop("database", None)
            if saved is not None:
                sys.modules["database"] = saved

    STS = [("SQL1 %s", (1,)), ("SQL2 %s %s", (2, 3)), ("SQL3", ())]

    def test_全部成功したら順に実行してcommitを1回しcloseする(self):
        conn = FakeConn()
        with mock.patch.object(self.db, "get_connection", return_value=conn):
            self.assertIsNone(self.db.execute_in_transaction(self.STS))
        self.assertEqual(conn.log, [("execute", "SQL1 %s", (1,)), ("execute", "SQL2 %s %s", (2, 3)),
                                    ("execute", "SQL3", ()), ("commit",), ("close",)])

    def test_途中で失敗したらrollbackして例外を出しcloseする(self):
        conn = FakeConn(fail_at=2)
        with mock.patch.object(self.db, "get_connection", return_value=conn):
            with self.assertRaises(RuntimeError):
                self.db.execute_in_transaction(self.STS)
        names = [x[0] for x in conn.log]
        self.assertEqual(names, ["execute", "execute", "rollback", "close"])   # 3つ目は実行しない
        self.assertNotIn("commit", names)

    def test_共有の保存文をそのまま流せる(self):
        conn = FakeConn()
        sts = shares.build_insert_statements(str(uuid.uuid4()), COND, RESULTS)
        with mock.patch.object(self.db, "get_connection", return_value=conn):
            self.db.execute_in_transaction(sts)
        self.assertEqual([(x[1], x[2]) for x in conn.log if x[0] == "execute"], sts)
        self.assertEqual([x[0] for x in conn.log][-2:], ["commit", "close"])


# ── テーブル定義（DDL） ───────────────────────────────────
class TestFR7DDL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DDL_003.read_text(encoding="utf-8")
        cls.active = active_sql_lines(cls.text)

    def body(self, table):
        return re.search(rf"CREATE TABLE IF NOT EXISTS {table}\s*\((.*?)\n\)\s*;", self.active, re.S).group(1)

    def cols(self, table):
        return re.findall(r"(?m)^\s*`?([a-z_]+)`?\s+(?:CHAR|VARCHAR|DATETIME|INT|TINYINT|DECIMAL|TEXT|BIGINT)",
                          self.body(table))

    def test_share_listsの10列(self):
        self.assertEqual(self.cols("share_lists"),
                         ["share_id", "created_at", "expires_at", "scene_tag", "relationship",
                          "preference_knowledge", "total_budget", "num_givers", "handover", "theme_ids"])
        self.assertRegex(self.body("share_lists"), r"share_id\s+CHAR\(36\)\s+NOT NULL PRIMARY KEY")
        self.assertRegex(self.body("share_lists"), r"created_at\s+DATETIME\s+NOT NULL DEFAULT CURRENT_TIMESTAMP")
        self.assertRegex(self.body("share_lists"), r"theme_ids\s+VARCHAR\(\d+\)\s+NULL")

    def test_share_list_itemsの5列と複合主キー(self):
        self.assertEqual(self.cols("share_list_items"), ["share_id", "rank", "product_id", "score", "reason_text"])
        body = self.body("share_list_items")
        self.assertIn("PRIMARY KEY (share_id, `rank`)", body)
        self.assertRegex(body, r"reason_text\s+TEXT\s+NOT NULL")

    def test_外部キー2本(self):
        body = self.body("share_list_items")
        self.assertRegex(body, r"FOREIGN KEY \(share_id\) REFERENCES share_lists\(share_id\)")
        self.assertRegex(body, r"FOREIGN KEY \(product_id\) REFERENCES products\(product_id\)")

    def test_rankは常にバッククォートで囲む(self):
        self.assertIsNone(re.search(r"(?<!`)\brank\b(?!`)", self.active))

    def test_event_logsへの外部キーは003で実行される行にある(self):
        alter = "ALTER TABLE event_logs ADD CONSTRAINT fk_event_share FOREIGN KEY (share_id) REFERENCES share_lists(share_id);"
        self.assertIn(alter, self.active)
        self.assertEqual(self.active.count("fk_event_share"), 1)
        # share_lists を作った後にある
        self.assertGreater(self.active.index(alter), self.active.index("CREATE TABLE IF NOT EXISTS share_lists"))

    def test_002では同じALTERがコメントのまま(self):
        text = DDL_002.read_text(encoding="utf-8")
        self.assertIn("fk_event_share", text)
        self.assertNotIn("fk_event_share", active_sql_lines(text))           # 二重に実行されない

    def test_個人情報らしい列がない(self):
        cols = self.cols("share_lists") + self.cols("share_list_items")
        for pii in ("name", "email", "episode", "episode_text", "phone", "address", "ip", "user_agent",
                    "recipient", "giver", "caution"):
            self.assertNotIn(pii, cols)
        self.assertNotRegex(self.active.lower(), r"\bepisode\w*\s+(?:text|varchar)")


# ── ルートの存在（FR-7 ログインなしで閲覧） ─────────────────────
class TestFR7Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_db = types.ModuleType("database")
        fake_db.fetch_all = lambda sql, params=(): []
        with mock.patch.dict(sys.modules, {"database": fake_db}), \
             mock.patch("dotenv.load_dotenv", lambda *a, **k: False):
            sys.modules.pop("main", None)
            main = importlib.import_module("main")
            cls.spec = main.app.openapi()
            cls.app = main.app

    def test_発行と閲覧のルートがある(self):
        paths = self.spec["paths"]
        self.assertIn("post", paths["/api/shares"])
        self.assertIn("get", paths["/api/shares/{share_id}"])

    def test_閲覧のshare_idはformat_uuid(self):
        params = self.spec["paths"]["/api/shares/{share_id}"]["get"]["parameters"]
        p = next(x for x in params if x["name"] == "share_id")
        self.assertEqual(p["in"], "path")
        self.assertEqual(p["schema"].get("format"), "uuid")

    def test_ログインを求めない(self):
        for path, method in (("/api/shares", "post"), ("/api/shares/{share_id}", "get")):
            self.assertNotIn("security", self.spec["paths"][path][method])
        self.assertNotIn("securitySchemes", self.spec.get("components", {}))

    def test_発行の入力はRecommendationRequest_出力はShareCreateResponse(self):
        op = self.spec["paths"]["/api/shares"]["post"]
        self.assertTrue(op["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/RecommendationRequest"))
        self.assertTrue(op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ShareCreateResponse"))
        op = self.spec["paths"]["/api/shares/{share_id}"]["get"]
        self.assertTrue(op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ShareResponse"))


# ── 画面と API の整合 ─────────────────────────────────────
class TestFR7FrontBackSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ts = FRONT_TYPES_TS.read_text(encoding="utf-8")

    def ts_fields(self, name):
        body = re.search(rf"export interface {name}\s*\{{(.*?)\n\}}", self.ts, re.S).group(1)
        return re.findall(r"(?m)^\s*([a-z_]+)\??\s*:", body)

    def test_ShareCreateResponseの項目名が一致する(self):
        self.assertEqual(self.ts_fields("ShareCreateResponse"), list(ShareCreateResponse.model_fields))

    def test_ShareItemの項目名が一致する(self):
        self.assertEqual(self.ts_fields("ShareItem"), list(ShareItem.model_fields))

    def test_ShareResponseの項目名が一致する(self):
        self.assertEqual(self.ts_fields("ShareResponse"), list(ShareResponse.model_fields))


if __name__ == "__main__":
    unittest.main()
