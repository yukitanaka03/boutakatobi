"use client";

// app/share/[share_id]/ShareViewLogger.tsx — 共有ページが開かれたことを利用ログに1回送る（FR-9 の share_view）
// 画面には何も表示しない。共有ページ本体は Server Component なので、ブラウザで動く部分だけここに分けた。

import { useEffect, useRef } from "react";
import { logEvent } from "@/lib/events";

export default function ShareViewLogger({ shareId }: { shareId: string }) {
  // 開発中は React の Strict Mode で useEffect が2回動く（Next.js の App Router は既定で有効）。
  // 2回目は送らないように、送ったかどうかを覚えておく
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    logEvent("share_view", { shareId });
  }, [shareId]);

  return null;
}
