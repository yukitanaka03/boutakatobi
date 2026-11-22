-- sql/002_create_event_logs.sql — 利用ログのテーブル（要件定義書 5.2 の DR-7、FR-9）
-- 【実行は人が MySQL Workbench で行う】AGENTS.md 4章12。AI はこのファイルを案として作るまで。
-- 班のDBは共有資産なので、実行する前に班で合意する。
-- エピソードの原文・氏名などの個人情報は持たない（NFR-1・NFR-7）。記録するのは「誰か分からない利用の単位」と操作の種類だけ。

CREATE TABLE IF NOT EXISTS event_logs (
    event_id   BIGINT      NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT 'イベントのID（連番）',
    session_id CHAR(36)    NOT NULL COMMENT '利用の単位。初回アクセス時に画面が発行する UUID',
    event_type VARCHAR(20) NOT NULL COMMENT 'input_submit/episode_submit/results_view/share_create/share_view/product_click',
    share_id   CHAR(36)    NULL     COMMENT '関連する共有ページの UUID。共有に関係ない操作は NULL',
    product_id VARCHAR(10) NULL     COMMENT '関連する商品（例 G0001）。商品に関係ない操作は NULL',
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作の日時（DB が入れる）',
    CONSTRAINT fk_event_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    INDEX idx_event_session (session_id, created_at)  -- 1回の利用の操作をまとめて時系列で引くため（DR-7 の確認方法）
);

-- share_id → share_lists の外部キーは、今は付けない。
-- share_lists は FR-7（共有）で作るテーブルでまだ無いため、付けるとこの CREATE が失敗する。
-- 次の文は 003_create_share_tables.sql の末尾で share_lists を作った後に実行する（ここでは実行しない）。
-- ALTER TABLE event_logs ADD CONSTRAINT fk_event_share FOREIGN KEY (share_id) REFERENCES share_lists(share_id);
