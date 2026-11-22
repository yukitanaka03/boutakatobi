// lib/events.ts — 利用ログを API（POST /api/events）に送る（FR-9）
// ログが取れなくても買い物の体験は止めない：待たない・失敗しても画面にエラーを出さない。

import { getSessionId } from "@/lib/session";

// 操作の種類。backend の schemas.py の EventType と並び・綴りをそろえる（片方だけ変えないこと）
export type EventType =
  | "input_submit" // 状況入力
  | "episode_submit" // エピソード入力
  | "results_view" // 候補表示
  | "share_create" // 共有の発行
  | "share_view" // 共有の閲覧
  | "product_click"; // 商品ページへ移動

// API の場所（lib/api.ts と同じ）
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function logEvent(
  eventType: EventType,
  opts: { shareId?: string; productId?: string } = {},
): void {
  const sessionId = getSessionId();
  if (!sessionId) return; // 利用の単位が無いと、つながりが分からないので送らない

  // await しない（画面を待たせない）。keepalive は、商品ページへ移動してページが閉じても送信を続けるため
  fetch(`${API}/api/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      event_type: eventType,
      share_id: opts.shareId ?? null,
      product_id: opts.productId ?? null,
    }),
    keepalive: true,
  }).catch((e) => console.warn("利用ログを送れませんでした", e));
}
