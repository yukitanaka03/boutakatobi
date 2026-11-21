# tests/test_fr9_events.py — FR-9（利用ログの記録）と DR-7（セッションでのつながり）のテスト
#
# 要件定義書の「確認方法」をそのままテストにしている。
#   FR-9：一連の操作を行い、6種類のイベントがすべて記録されるか
#   DR-7：セッションIDで、1回の利用の操作がつながって記録されているか
#   NFR-1・NFR-7：エピソード原文・個人情報を受け取らない・保存しない
#   AGENTS.md：SQL の値は %s プレースホルダ＋params で渡す
# 班のDBにはつながない。DBを呼ぶ部分は偽物（fake）に差し替えて、渡すSQLと値だけを確かめる。
# 実行：backend フォルダで  python -m unittest discover -s tests -t . -v

import re
import sys
import types
import typing
import unittest
import uuid
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError

import schemas
from routers import events
from schemas import EventRequest, EventResponse

BACKEND_DIR = Path(__file__).resolve().parent.parent
DDL_PATH = BACKEND_DIR / "sql" / "002_create_event_logs.sql"
FRONT_EVENTS_TS = BACKEND_DIR.parent / "giftia-frontend" / "lib" / "events.ts"

SIX_TYPES = ["input_submit", "episode_submit", "results_view", "share_create", "share_view", "product_click"]


def recording_db():
    """execute に渡された (sql, params) を記録するだけの偽 database モジュール"""
    calls = []
    fake_db = types.ModuleType("database")
    fake_db.execute = lambda sql, params=(): calls.append((sql, params))
    return fake_db, calls


def failing_db():
    fake_db = types.ModuleType("database")

    def execute(sql, params=()):
        raise RuntimeError("接続できません")

    fake_db.execute = execute
    return fake_db


def one_session_requests(session_id, share_id):
    """1回の利用で起きる一連の操作（状況入力 → エピソード → 候補表示 → 共有発行 → 共有閲覧 → 商品ページへ）"""
    return [
        {"session_id": session_id, "event_type": "input_submit"},
        {"session_id": session_id, "event_type": "episode_submit"},
        {"session_id": session_id, "event_type": "results_view"},
        {"session_id": session_id, "event_type": "share_create", "share_id": share_id},
        {"session_id": session_id, "event_type": "share_view", "share_id": share_id},
        {"session_id": session_id, "event_type": "product_click", "product_id": "G0001"},
    ]


def active_sql_lines(text):
    """SQL ファイルからコメント（-- 以降）を除いた、実際に実行される部分だけを返す"""
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


# ── FR-9 / DR-7 一連の操作が記録される ──────────────────────
class TestFR9Record(unittest.TestCase):
    def test_6種類の操作がすべて同じセッションIDで記録される(self):
        session_id = str(uuid.uuid4())
        share_id = str(uuid.uuid4())
        fake_db, calls = recording_db()
        with mock.patch.dict(sys.modules, {"database": fake_db}):
            for body in one_session_requests(session_id, share_id):
                events.create_event(EventRequest(**body))

        self.assertEqual(len(calls), 6)                                     # 6回記録された
        rows = [params for _, params in calls]
        self.assertEqual([r[1] for r in rows], SIX_TYPES)                   # 6種類が操作順にそろう（FR-9）
        self.assertEqual(set(r[1] for r in rows), set(SIX_TYPES))
        for sid, *_ in rows:                                                # 全部同じ利用の単位（DR-7）
            self.assertIsInstance(sid, str)
            self.assertEqual(sid, session_id)
        for sql, _ in calls:
            self.assertEqual(sql, events.INSERT_SQL)

    def test_共有の操作には共有ID_商品ページへは商品IDが入り他はNone(self):
        session_id = str(uuid.uuid4())
        share_id = str(uuid.uuid4())
        fake_db, calls = recording_db()
        with mock.patch.dict(sys.modules, {"database": fake_db}):
            for body in one_session_requests(session_id, share_id):
                events.create_event(EventRequest(**body))
        by_type = {params[1]: params for _, params in calls}
        for t in ("input_submit", "episode_submit", "results_view"):
            self.assertEqual(by_type[t], (session_id, t, None, None))
        self.assertEqual(by_type["share_create"], (session_id, "share_create", share_id, None))
        self.assertEqual(by_type["share_view"], (session_id, "share_view", share_id, None))
        self.assertEqual(by_type["product_click"], (session_id, "product_click", None, "G0001"))
        self.assertIsInstance(by_type["share_create"][2], str)              # UUID 型のままではなく文字列で渡す

    def test_別の利用は別のセッションIDで区別される(self):
        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        fake_db, calls = recording_db()
        with mock.patch.dict(sys.modules, {"database": fake_db}):
            events.create_event(EventRequest(session_id=a, event_type="input_submit"))
            events.create_event(EventRequest(session_id=b, event_type="input_submit"))
        self.assertEqual([p[0] for _, p in calls], [a, b])

    def test_記録できたら_ok_True_を返す(self):
        fake_db, _ = recording_db()
        with mock.patch.dict(sys.modules, {"database": fake_db}):
            out = events.create_event(EventRequest(session_id=str(uuid.uuid4()), event_type="results_view"))
        self.assertEqual(out, {"ok": True})
        self.assertEqual(EventResponse(**out).ok, True)                     # response_model の形に合う


# ── SQL の値はプレースホルダで渡す（AGENTS.md） ─────────────────
class TestFR9SQL(unittest.TestCase):
    def test_INSERT文は4つの_s_を使い値を埋め込んでいない(self):
        sql = events.INSERT_SQL
        self.assertEqual(sql.count("%s"), 4)
        self.assertIn("INSERT INTO event_logs (session_id, event_type, share_id, product_id)", sql)
        self.assertIn("VALUES (%s, %s, %s, %s)", sql)
        self.assertNotIn("{", sql)                                          # f文字列・format の跡がない
        self.assertNotIn("'", sql)                                          # 値を引用符で埋め込んでいない

    def test_値はSQLと別のparamsで渡り_SQLは入力で変わらない(self):
        session_id = str(uuid.uuid4())
        fake_db, calls = recording_db()
        with mock.patch.dict(sys.modules, {"database": fake_db}):
            events.create_event(EventRequest(session_id=session_id, event_type="product_click", product_id="G12345678"))
        sql, params = calls[0]
        self.assertIs(sql, events.INSERT_SQL)                               # 同じ固定の文字列
        self.assertNotIn(session_id, sql)
        self.assertNotIn("G12345678", sql)
        self.assertIsInstance(params, tuple)
        self.assertEqual(len(params), 4)


# ── 入力チェック（422 相当） ──────────────────────────────
class TestFR9Validation(unittest.TestCase):
    def setUp(self):
        self.sid = str(uuid.uuid4())

    def assertRejected(self, **body):
        with self.assertRaises(ValidationError, msg=str(body)):
            EventRequest(**body)

    def test_6種類以外の操作は受け付けない(self):
        for bad in ("page_view", "", "INPUT_SUBMIT", "input_submit ", None):
            self.assertRejected(session_id=self.sid, event_type=bad)

    def test_6種類はすべて受け付ける(self):
        sh = str(uuid.uuid4())
        for body in one_session_requests(self.sid, sh):
            EventRequest(**body)

    def test_セッションIDがUUIDでなければ受け付けない(self):
        for bad in ("abc", "", "12345", "x" * 36, "taro@example.com"):
            self.assertRejected(session_id=bad, event_type="input_submit")

    def test_セッションIDが無ければ受け付けない(self):
        self.assertRejected(event_type="input_submit")

    def test_共有の操作で共有IDが無ければ受け付けない(self):
        for t in ("share_create", "share_view"):
            self.assertRejected(session_id=self.sid, event_type=t)
            self.assertRejected(session_id=self.sid, event_type=t, share_id=None)

    def test_共有IDがUUIDでなければ受け付けない(self):
        self.assertRejected(session_id=self.sid, event_type="share_view", share_id="share-1")

    def test_商品ページへの移動で商品IDが無ければ受け付けない(self):
        self.assertRejected(session_id=self.sid, event_type="product_click")
        self.assertRejected(session_id=self.sid, event_type="product_click", product_id=None)

    def test_商品IDの形式が違えば受け付けない(self):
        for bad in ("X1", "G1", "G123", "G123456789", "g0001", "G00A1", " G0001", "G0001 ",
                    "G0001'; DROP TABLE", "G0001' OR '1'='1", "G0001\n"):
            self.assertRejected(session_id=self.sid, event_type="product_click", product_id=bad)

    def test_商品IDの正しい形式は受け付ける(self):
        for ok in ("G0001", "G12345678"):
            req = EventRequest(session_id=self.sid, event_type="product_click", product_id=ok)
            self.assertEqual(req.product_id, ok)

    def test_決めていない項目は受け付けない_エピソード原文や氏名(self):
        for extra in ({"episode": "送別会で泣いてくれた先輩"}, {"name": "山田太郎"},
                      {"email": "taro@example.com"}, {"episode_text": "…"}):
            self.assertRejected(session_id=self.sid, event_type="episode_submit", **extra)

    def test_入力が不正ならDBに書き込まれない(self):
        fake_db, calls = recording_db()
        with mock.patch.dict(sys.modules, {"database": fake_db}):
            with self.assertRaises(ValidationError):
                events.create_event(EventRequest(session_id="abc", event_type="input_submit"))
        self.assertEqual(calls, [])


# ── DB が止まっているとき ─────────────────────────────────
class TestFR9DBError(unittest.TestCase):
    def test_DBが例外を投げたら503で入力値をエラー文に出さない(self):
        session_id = str(uuid.uuid4())
        share_id = str(uuid.uuid4())
        with mock.patch.dict(sys.modules, {"database": failing_db()}):
            with self.assertRaises(HTTPException) as cm:
                events.create_event(EventRequest(session_id=session_id, event_type="share_view", share_id=share_id))
        self.assertEqual(cm.exception.status_code, 503)
        detail = str(cm.exception.detail)
        self.assertNotIn(session_id, detail)
        self.assertNotIn(share_id, detail)
        self.assertNotIn("接続できません", detail)                           # 内部の例外文も出さない

    def test_商品IDもエラー文に出さない(self):
        with mock.patch.dict(sys.modules, {"database": failing_db()}):
            with self.assertRaises(HTTPException) as cm:
                events.create_event(EventRequest(session_id=str(uuid.uuid4()), event_type="product_click",
                                                 product_id="G0042"))
        self.assertEqual(cm.exception.status_code, 503)
        self.assertNotIn("G0042", str(cm.exception.detail))


# ── テーブル定義（DDL） ───────────────────────────────────
class TestFR9DDL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DDL_PATH.read_text(encoding="utf-8")
        cls.active = active_sql_lines(cls.text)

    def test_event_logsの6列がある(self):
        self.assertRegex(self.active, r"CREATE TABLE IF NOT EXISTS event_logs\s*\(")
        for col in ("event_id", "session_id", "event_type", "share_id", "product_id", "created_at"):
            self.assertRegex(self.active, rf"(?m)^\s*{col}\s+\w+", col)

    def test_列は6つだけで個人情報らしい列がない(self):
        body = re.search(r"CREATE TABLE IF NOT EXISTS event_logs\s*\((.*)\)\s*;", self.active, re.S).group(1)
        cols = re.findall(r"(?m)^\s*([a-z_]+)\s+(?:BIGINT|CHAR|VARCHAR|DATETIME|INT|TEXT)", body)
        self.assertEqual(cols, ["event_id", "session_id", "event_type", "share_id", "product_id", "created_at"])
        for pii in ("name", "email", "episode", "phone", "address", "ip", "user_agent", "text"):
            self.assertNotIn(pii, cols)

    def test_productsへの外部キーがある(self):
        self.assertRegex(self.active, r"FOREIGN KEY \(product_id\) REFERENCES products\(product_id\)")

    def test_セッションと日時の索引がある(self):
        self.assertRegex(self.active, r"INDEX \w+ \(session_id, created_at\)")

    def test_share_listsへの外部キーは実行される行にない(self):
        self.assertIn("share_lists", self.text)                             # 案としてコメントには書いてある
        self.assertNotIn("share_lists", self.active)                        # 実行される部分にはない

    def test_列の型がAPIの入力制限と合う(self):
        self.assertRegex(self.active, r"session_id\s+CHAR\(36\)\s+NOT NULL")  # UUID の文字列は36文字
        self.assertRegex(self.active, r"share_id\s+CHAR\(36\)\s+NULL")
        self.assertRegex(self.active, r"product_id\s+VARCHAR\(10\)\s+NULL")    # max_length=10 と同じ
        width = int(re.search(r"event_type\s+VARCHAR\((\d+)\)", self.active).group(1))
        self.assertGreaterEqual(width, max(len(t) for t in SIX_TYPES))       # 一番長い種類名が入る


# ── 画面と API の整合 ─────────────────────────────────────
class TestFR9FrontBackSync(unittest.TestCase):
    def test_画面のEventTypeとAPIのEventTypeが同じ6種類で同じ並び(self):
        ts = FRONT_EVENTS_TS.read_text(encoding="utf-8")
        block = re.search(r"export type EventType\s*=(.*?);", ts, re.S).group(1)
        front = re.findall(r'"([a-z_]+)"', block)
        back = list(typing.get_args(schemas.EventType))
        self.assertEqual(front, back)
        self.assertEqual(back, SIX_TYPES)

    def test_画面が送る項目名がAPIの項目名と一致する(self):
        ts = FRONT_EVENTS_TS.read_text(encoding="utf-8")
        body = re.search(r"JSON\.stringify\(\{(.*?)\}\)", ts, re.S).group(1)
        keys = re.findall(r"(?m)^\s*([a-z_]+)\s*:", body)
        self.assertEqual(set(keys), set(EventRequest.model_fields))


if __name__ == "__main__":
    unittest.main()
