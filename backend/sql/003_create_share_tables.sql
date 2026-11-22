-- sql/003_create_share_tables.sql — 共有ページのテーブル（要件定義書 5.2 の DR-5・DR-6、FR-7）
-- 【実行は人が MySQL Workbench で行う】AGENTS.md 4章12。AI はこのファイルを案として作るまで。
-- 班のDBは共有資産なので、実行する前に班で合意する。
-- 実行順は 002 → 003（末尾で 002 の event_logs に外部キーを足すため、event_logs が先に要る）。
-- エピソードの原文・氏名などの個人情報は持たない（NFR-1・NFR-7）。テーマは theme_id だけを残す。

-- 共有を発行するたびに1行（DR-5）。share_id は推測されにくい UUID で、共有ページの URL に使う
CREATE TABLE IF NOT EXISTS share_lists (
    share_id             CHAR(36)     NOT NULL PRIMARY KEY COMMENT '共有ページのID（UUID）。URL /share/{share_id} に使う',
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '発行日時（DB が入れる）',
    expires_at           DATETIME     NOT NULL COMMENT '閲覧期限（発行から30日）',
    scene_tag            VARCHAR(10)  NOT NULL COMMENT '利用シーン（今は 送別 のみ）',
    relationship         VARCHAR(10)  NOT NULL COMMENT 'senior/peer/boss/junior/client',
    preference_knowledge VARCHAR(4)   NOT NULL COMMENT '好みの把握度 low/mid/high',
    total_budget         INT          NOT NULL COMMENT '贈り手全員の合計予算（円）',
    num_givers           TINYINT      NOT NULL COMMENT '連名で贈る人数',
    handover             VARCHAR(4)   NOT NULL COMMENT '渡し方 hand/ship',
    theme_ids            VARCHAR(255) NULL     COMMENT 'theme_id のカンマ区切り。NULL=入力なし（エピソード原文は保存しない）'
);

-- 共有した候補を順位ごとに1行（DR-6）。理由文は共有した時点のものを固定して持つ
-- （後で商品属性や理由の作り方が変わっても、共有ページの表示が変わらないようにするため）
-- rank は MySQL 8 の予約語なので、このファイルでは常に `rank` とバッククォートで囲む
CREATE TABLE IF NOT EXISTS share_list_items (
    share_id    CHAR(36)     NOT NULL COMMENT '共有ページのID（share_lists）',
    `rank`      TINYINT      NOT NULL COMMENT '順位（1〜5）',
    product_id  VARCHAR(10)  NOT NULL COMMENT '商品ID（例 G0001）',
    score       DECIMAL(5,4) NOT NULL COMMENT '外れにくさの点（0〜1）。API の score は小数4桁なのでそのまま保存',
    reason_text TEXT         NOT NULL COMMENT '共有時点で表示した理由文（複数は改行区切り）',
    PRIMARY KEY (share_id, `rank`),
    CONSTRAINT fk_share_item_list FOREIGN KEY (share_id) REFERENCES share_lists(share_id),
    CONSTRAINT fk_share_item_product FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 002 で後回しにしていた外部キー（event_logs.share_id → share_lists）。share_lists ができたのでここで足す
ALTER TABLE event_logs ADD CONSTRAINT fk_event_share FOREIGN KEY (share_id) REFERENCES share_lists(share_id);
