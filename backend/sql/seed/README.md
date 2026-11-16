# sql/seed — 班のDBに入れるデータ（CSV）

| ファイル | 入れ先のテーブル | 中身 |
|---|---|---|
| `product_attributes.csv` | product_attributes | 商品ごとの「外れにくさの属性」。今週は人が手で付ける（FR-8 の生成AI推定は来週以降） |
| `reason_templates.csv` | reason_templates | 理由文・注意点の定型文（FR-6） |

**`product_attributes.csv` が見出し行だけだと、候補は必ず0件になる**（FR-3 は属性が付いた商品だけを取るため）。

## product_attributes.csv の書き方（要件定義書 5.2）

1行＝1商品。見出し行は変えない。文字コードは UTF-8 で保存する。

| 列 | 入れる値 | 補足 |
|---|---|---|
| product_id | 商品ID（例 G0001） | products にある ID。重複させない |
| preference_dependency | low / mid / high | 好みへの依存度。タオル=low、ハンドクリーム=high |
| scent_level | none / weak / strong | 香りの強さ |
| room_temp_ok | 1 / 0 | 常温で保存できるか。要冷蔵は 0 |
| individually_wrapped | 1 / 0 / 空欄 | 個包装か。食品以外は空欄 |
| shelf_life_days | 0以上の整数 / 空欄 | 賞味期限までの最短日数。食品以外は空欄 |
| carry_size | small / medium / large | small=手提げに入る、medium=紙袋が必要、large=持ち帰りが負担 |
| shareable | 1 / 0 | 複数人で分けられるか |
| workplace_friendly | 1 / 0 | **自分で判断しない。** room_temp_ok=1 かつ carry_size が large 以外 かつ scent_level が strong 以外 のとき 1、それ以外は 0 |
| style | standard / unique | 定番か個性的か |
| source | manual | 人が付けたので manual |
| confidence | 空欄 | manual のときは空欄 |
| reviewed_at | 空欄 または 日付（2026-11-20） | 商品部が確認した日 |

例（1行）：

```
G0001,low,none,1,,,small,0,1,standard,manual,,
```

## 書き間違いのチェック（DBに入れる前に）

backend フォルダで次を実行する。取りうる値以外・IDの重複・workplace_friendly のルール違反があると、どの商品のどの列かが表示される。

```bash
python -m unittest tests.test_fr3_fr6 -v
```

## DBへの入れ方

AI は班のDBに接続しない（AGENTS.md 4章12）。**班で合意したうえで、人が MySQL Workbench で行う。**

1. `sql/001_create_tables.sql` を実行してテーブルを作る
2. テーブルを右クリック → Table Data Import Wizard で CSV を読み込む
3. 空欄にした列（individually_wrapped など）が NULL で入ったかを確認する

## 属性を付ける商品の選び方（SQL の案。実行は人が Workbench で）

送別タグ付き・在庫ありの商品を、送別での購入数（直近1年）が多い順に並べる。上位から付ける。

```sql
SELECT p.product_id, p.product_name, p.category, p.price, COUNT(DISTINCT o.order_id) AS sobetsu_orders
FROM products p
JOIN product_scenes ps ON ps.product_id = p.product_id AND ps.scene_tag = '送別'
LEFT JOIN order_items oi ON oi.product_id = p.product_id
LEFT JOIN orders o ON o.order_id = oi.order_id
     AND o.estimated_scene = '送別'
     AND o.ordered_at >= (SELECT DATE_SUB(MAX(ordered_at), INTERVAL 1 YEAR) FROM orders)
WHERE p.stock > 0
GROUP BY p.product_id, p.product_name, p.category, p.price
ORDER BY sobetsu_orders DESC, p.product_id
LIMIT 50;
```

テストケース（要件定義書 6.4 の No.1・No.5）を確かめるには、3,150〜4,500円 と 10,500〜15,000円 の価格帯に、それぞれ5件以上は属性を付けておく。
