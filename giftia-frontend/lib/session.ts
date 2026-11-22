// lib/session.ts — 1回の利用を表す ID（session_id）を用意する（FR-9・DR-7）
// sessionStorage に置く＝タブを閉じると消える。タブを開いてから閉じるまでを「1回の利用」とみなす。
// 中身はランダムな UUID だけ。氏名などの個人情報は入れない（NFR-7）。

const KEY = "giftia_session_id";

// sessionStorage が使えない環境（プライベートモード等）用。このページを表示している間だけ覚えておく
let fallbackId = "";

export function getSessionId(): string {
  // サーバー側では呼ばれない想定。念のため空文字を返す（空なら利用ログは送らない）
  if (typeof window === "undefined") return "";

  try {
    const saved = window.sessionStorage.getItem(KEY);
    if (saved) return saved;
    const id = crypto.randomUUID();
    window.sessionStorage.setItem(KEY, id);
    return id;
  } catch {
    if (!fallbackId) fallbackId = crypto.randomUUID();
    return fallbackId;
  }
}
