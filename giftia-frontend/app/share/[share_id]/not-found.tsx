// app/share/[share_id]/not-found.tsx — 共有ページが見つからないときの表示（FR-7）
// page.tsx で notFound() を呼ぶとこれが表示される（HTTP の状態は 404）。URL の打ち間違いや存在しない ID のとき。

import styles from "./page.module.css";

export default function ShareNotFound() {
  return (
    <main className={styles.main}>
      <div className={styles.panel}>
        <h1 className={styles.title}>共有ページが見つかりません</h1>
        <p className={styles.lead}>URLが正しいか、共有した人に確認してください。</p>
      </div>
    </main>
  );
}
