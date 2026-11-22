"use client";

// app/share/[share_id]/ProductLink.tsx — 商品ページへのリンク。押されたら利用ログ（product_click）を送ってから移動する（FR-9）
// logEvent は keepalive 付きで送るので、ページを移動しても送信は続く（待たずに移動してよい）。

import Link from "next/link";
import type { ReactNode } from "react";
import { logEvent } from "@/lib/events";

type Props = {
  productId: string;
  shareId: string;
  children: ReactNode;
  className?: string;
};

export default function ProductLink({ productId, shareId, children, className }: Props) {
  return (
    <Link
      // Phase1 のモック用の仮URL。商品ページの形式が決まったら差し替える
      href={`/products/${productId}`}
      className={className}
      onClick={() => logEvent("product_click", { productId, shareId })}
    >
      {children}
    </Link>
  );
}
