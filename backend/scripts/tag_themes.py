# scripts/tag_themes.py — 商品の名前と説明文から「関連するテーマ」を付ける（FR-8 の Phase1 版、DR-3）
#
# 入力：Workbench で書き出した商品のCSV（tag_products.py と同じもの）
# 出力：sql/seed/product_themes.csv（要件定義書 5.2 の形。読み込みは人が Workbench で行う）
#
#   python scripts/tag_themes.py <書き出したCSV> [出力先]
#
# テーマの語彙は sql/seed/theme_tags.csv（20語）。エピソードから取り出すテーマ（FR-2）と同じ語彙を使う。
# 商品名のうちブランド名は見ない（「Outdoor Life Nagi 保温ボトル」はアウトドアの商品ではない）。
# 説明文の決まり文句（「カタログは写真の多い冊子です」など）で付かないよう、言い回しまで含めて書く。
# 商品名で当たったものは確からしさ 0.9、説明文だけで当たったものは 0.7。商品部は 0.7 から確認する。

import csv
import re
import sys
from pathlib import Path

OUT_COLUMNS = ["product_id", "theme_id", "source", "confidence"]

# theme_id → 当てはまる言い回し（正規表現）
RULES = {
    "T001": r"コーヒー|珈琲|ドリップバッグ|焙煎",
    "T002": r"紅茶|アールグレイ|ダージリン|ハーブティー|ティーバッグ",
    "T003": r"日本茶|緑茶|煎茶|ほうじ茶|抹茶|狭山茶|玉露|急須",
    "T004": r"焼き菓子|クッキー|チョコ|ショコラ|バウム|マドレーヌ|フィナンシェ|ケーキ|和菓子|羊羹|カステラ|スイーツ|甘いもの",
    "T005": r"ワイン(?!レッド)|日本酒|ビール|麦酒|ウイスキー|焼酎|晩酌",
    "T006": r"キャンプ|アウトドア|山登り|登山|ハイキング|焚き火|テント|ランタン",
    "T007": r"花束|ブーケ|フラワー|プリザーブド|ドライフラワー|観葉植物|植物|鉢植え|生花|季節の花",
    "T008": r"入浴|バスソルト|バスボム|お風呂|湯船|リラックス|アロマ",
    "T009": r"デスク|在宅|パソコン|オフィスで使",   # 「オフィスでもお渡ししやすい」は渡し方の話なので含めない
    "T010": r"ボールペン|万年筆|手帳|ノート|便箋|レターセット|文具",
    "T011": r"名刺|営業|外回り|商談",
    "T012": r"フォトフレーム|写真立て|アルバム|写真を入れ|写真を飾",
    "T013": r"ハンドクリーム|ハンドケア|手肌",
    "T014": r"スキンケア|化粧水|美容液|保湿クリーム|ボディクリーム|(?<!ド)リップ",
    "T015": r"体験ギフト|体験の内容|体験から",
    "T016": r"マグカップ|タンブラー|保温ボトル|マイボトル",
    "T017": r"ねこ|猫|いぬ|犬|動物",
    "T018": r"睡眠|眠り|安眠|枕|おやすみ",
    "T019": r"健康|ヘルシー|ストレッチ|ヨガ|運動",
    "T020": r"本革|牛革|革小物|レザー|革の",
}


def themes_for(p: dict) -> list[dict]:
    name = p["product_name"].replace(p.get("brand") or "", "")
    desc = p["description"]
    rows = []
    for theme_id, pattern in RULES.items():
        if re.search(pattern, name):
            conf = 0.9
        elif re.search(pattern, desc):
            conf = 0.7
        else:
            continue
        rows.append({"product_id": p["product_id"], "theme_id": theme_id, "source": "ai", "confidence": f"{conf:.2f}"})
    return rows


def main(src: str, dst: str):
    with open(src, encoding="utf-8") as f:
        products = list(csv.DictReader(f))
    rows = [r for p in products for r in themes_for(p)]
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    tagged = len({r["product_id"] for r in rows})
    print(f"{len(rows)}件（{tagged}/{len(products)}商品にテーマあり）→ {dst}")


if __name__ == "__main__":
    default_out = Path(__file__).resolve().parent.parent / "sql" / "seed" / "product_themes.csv"
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else str(default_out))
