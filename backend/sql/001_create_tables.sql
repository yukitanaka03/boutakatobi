-- sql/001_create_tables.sql — 今週足すテーブル（要件定義書 5.2 の DR-1・DR-4）
-- 【実行は人が MySQL Workbench で行う】AGENTS.md 4章12。AI はこのファイルを案として作るまで。
-- 班のDBは共有資産なので、実行する前に班で合意する。

CREATE TABLE IF NOT EXISTS product_attributes (
    product_id            VARCHAR(10)  NOT NULL PRIMARY KEY,
    preference_dependency VARCHAR(4)   NOT NULL COMMENT 'low/mid/high：好みへの依存度',
    scent_level           VARCHAR(6)   NOT NULL COMMENT 'none/weak/strong：香りの強さ',
    room_temp_ok          TINYINT(1)   NOT NULL COMMENT '1=常温で保存できる',
    individually_wrapped  TINYINT(1)   NULL     COMMENT '1=個包装、0=非個包装、NULL=食品以外',
    shelf_life_days       INT          NULL     COMMENT '届いてから賞味期限までの最短日数。NULL=食品以外',
    carry_size            VARCHAR(6)   NOT NULL COMMENT 'small/medium/large：持ち帰りの大きさ',
    shareable             TINYINT(1)   NOT NULL COMMENT '1=複数人で分けられる',
    workplace_friendly    TINYINT(1)   NOT NULL COMMENT '1=常温・large以外・香りstrong以外',
    style                 VARCHAR(8)   NOT NULL COMMENT 'standard/unique：無難か個性的か',
    source                VARCHAR(6)   NOT NULL COMMENT 'ai/manual：付け方',
    confidence            DECIMAL(3,2) NULL     COMMENT 'AI推定の確からしさ。manual は NULL',
    reviewed_at           DATE         NULL     COMMENT '商品部が確認した日。NULL=未確認',
    CONSTRAINT fk_attr_product FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS reason_templates (
    template_id  VARCHAR(5)  NOT NULL PRIMARY KEY,
    target_type  VARCHAR(10) NOT NULL COMMENT 'attribute/theme/caution',
    target_key   VARCHAR(40) NOT NULL COMMENT '属性名・テーマID・注意点のキー',
    target_value VARCHAR(20) NOT NULL COMMENT '表示する条件の値（any=値を問わない）',
    text         VARCHAR(60) NOT NULL COMMENT '画面に出す文言。{n}{r}{days} は実際の値に置き換える'
);
-- reason_templates の中身は sql/seed/reason_templates.csv（Workbench の Table Data Import Wizard で読み込む）
-- 今は API が CSV を直接読んでいる（services/reasons.py）。DB に入れたら DB から読むように変える

-- FR-5（エピソードとの関連度）で使うテーブル（要件定義書 5.2 の DR-2・DR-3）
CREATE TABLE IF NOT EXISTS theme_tags (
    theme_id  VARCHAR(4)  NOT NULL PRIMARY KEY COMMENT 'T+3桁',
    name      VARCHAR(20) NOT NULL COMMENT 'エピソードと商品を結び付けるテーマ（趣味・習慣・生活シーン）'
);

CREATE TABLE IF NOT EXISTS product_themes (
    product_id  VARCHAR(10)  NOT NULL,
    theme_id    VARCHAR(4)   NOT NULL,
    source      VARCHAR(6)   NOT NULL COMMENT 'ai/manual：付け方',
    confidence  DECIMAL(3,2) NULL     COMMENT 'AI推定の確からしさ。manual は NULL',
    PRIMARY KEY (product_id, theme_id),
    CONSTRAINT fk_theme_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT fk_theme_tag     FOREIGN KEY (theme_id)   REFERENCES theme_tags(theme_id)
);
-- 中身は sql/seed/theme_tags.csv（語彙20語）と sql/seed/product_themes.csv（scripts/tag_themes.py で作る）
