# scripts/tag_products.py — 商品の説明文から「外れにくさの属性」を付ける（FR-8 の Phase1 版）
#
# 入力：Workbench で書き出した商品のCSV（product_id・product_name・category・price・size・description）
# 出力：sql/seed/product_attributes.csv（要件定義書 5.2 の形。読み込みは人が Workbench で行う）
#
#   python scripts/tag_products.py <書き出したCSV> [出力先]
#
# DBにはつながない（AGENTS.md 4章12）。説明文の【香り】【賞味期限】【包装】【保存方法】の見出しと、
# カテゴリーごとの既定値で付ける。根拠が説明文にある属性は確からしさ（confidence）を高く、
# カテゴリーの既定値で埋めた属性は低くする。商品部は confidence の低いものから確認する（要件定義書 5.4）。
# source は ai（人が確認したら manual に書き換え、reviewed_at に日付を入れる）。

import csv
import re
import sys
from pathlib import Path

FOOD = {"食品", "飲料"}
OUT_COLUMNS = ["product_id", "preference_dependency", "scent_level", "room_temp_ok", "individually_wrapped",
               "shelf_life_days", "carry_size", "shareable", "workplace_friendly", "style", "source",
               "confidence", "reviewed_at"]


def section(desc: str, name: str) -> str | None:
    m = re.search(rf"【{name}】([^\n]+)", desc)
    return m.group(1).strip() if m else None


def scent_level(p: dict) -> tuple[str, bool]:
    """香りの強さ。（値, 説明文に根拠があったか）"""
    s = section(p["description"], "香り")
    if s:
        if "しっかり" in s or "強" in s:
            return "strong", True
        return "weak", True              # 「ほのか」「ひかえめ」や、香りの名前だけのもの
    if p["category"] == "フラワー":
        return ("none", True) if re.search("プリザーブド|ドライ|ソープ", p["description"] + p["product_name"]) else ("weak", False)
    return "none", p["category"] not in ("コスメ",)


def shelf_life_days(p: dict) -> tuple[int | None, bool]:
    """届いてから賞味期限までの最短日数（食品以外は None）。製造日起点は発送までに15日かかるとみて差し引く。"""
    if p["category"] not in FOOD:
        return None, True
    s = section(p["description"], "賞味期限") or ""
    if m := re.search(r"発送日から(\d+)日", s):
        return int(m.group(1)), True
    if m := re.search(r"製造日より(\d+)日", s):
        return max(int(m.group(1)) - 15, 0), True
    if m := re.search(r"約(\d+)か月", s):
        return int(m.group(1)) * 30 - 15, True
    # 説明文に無いものは、品目ごとの控えめな目安（確認対象）
    name = p["product_name"]
    if re.search("ドリップ|コーヒー|珈琲|紅茶|茶|ティー", name):
        return 180, False
    if re.search("ショコラ|チョコ", name):
        return 60, False
    return 30, False


def preference_dependency(p: dict, scent: str) -> str:
    cat, desc, name = p["category"], p["description"], p["product_name"]
    if cat == "コスメ":
        return "high" if scent == "strong" else "mid"
    if cat == "カタログギフト":
        return "low"                       # 受け取った人が選ぶ
    if cat == "生活雑貨":
        return "mid" if re.search("名入れ|イニシャル|刺繍|ねこ", desc + name) else "low"
    if "好みを選ばない" in desc:
        return "low"
    return "mid"                           # 食品・飲料（味の好み）、フラワー、ビジネス小物（色・デザイン）


def carry_size(p: dict) -> str:
    size, name = p["size"], p["product_name"]
    if re.search(r"Lサイズ|^L$", size):
        return "large"
    if re.search(r"Mサイズ|高さ約45cm|バスタオル", size + name):
        return "medium"
    return "small"


def individually_wrapped(p: dict) -> str:
    if p["category"] not in FOOD:
        return ""
    return "1" if re.search("個包装|1個ずつ|小袋|ドリップバッグ", p["description"] + p["product_name"] + p["size"]) else "0"


def shareable(p: dict, wrapped: str) -> str:
    if wrapped == "1":
        return "1"
    m = re.search(r"(\d+)(個|袋|粒|枚)入", p["product_name"] + p["size"])
    return "1" if p["category"] in FOOD and m and int(m.group(1)) >= 6 else "0"


def style(p: dict) -> str:
    return "unique" if re.search("名入れ|デザイン|イニシャル|ことば|ねこ", p["description"] + p["product_name"]) else "standard"


def tag(p: dict) -> dict:
    scent, scent_known = scent_level(p)
    shelf, shelf_known = shelf_life_days(p)
    wrapped = individually_wrapped(p)
    room_temp = "0" if re.search(r"要冷蔵|冷蔵で保存|冷蔵庫で", p["description"]) else "1"
    size = carry_size(p)
    workplace = "1" if room_temp == "1" and size != "large" and scent != "strong" else "0"
    known = [scent_known, shelf_known]
    confidence = 0.9 if all(known) else 0.6
    return {
        "product_id": p["product_id"],
        "preference_dependency": preference_dependency(p, scent),
        "scent_level": scent,
        "room_temp_ok": room_temp,
        "individually_wrapped": wrapped,
        "shelf_life_days": "" if shelf is None else str(shelf),
        "carry_size": size,
        "shareable": shareable(p, wrapped),
        "workplace_friendly": workplace,
        "style": style(p),
        "source": "ai",
        "confidence": f"{confidence:.2f}",
        "reviewed_at": "",
    }


def main(src: str, dst: str):
    with open(src, encoding="utf-8") as f:
        products = list(csv.DictReader(f))
    rows = [tag(p) for p in products]
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)}件 → {dst}（確からしさ0.9：{sum(r['confidence'] == '0.90' for r in rows)}件、0.6：{sum(r['confidence'] == '0.60' for r in rows)}件）")


if __name__ == "__main__":
    default_out = Path(__file__).resolve().parent.parent / "sql" / "seed" / "product_attributes.csv"
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else str(default_out))
