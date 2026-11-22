// app/share/[share_id]/page.tsx — 共有ページ（FR-7、要件定義書 4.2）
// ログインなしで閲覧だけできるページ。入力条件・候補と理由文・各商品へのリンク・閲覧期限を表示する。
// Server Component（サーバーで HTML を作る）。ブラウザで動く利用ログの送信だけ ShareViewLogger・ProductLink に分けた。
// エピソードの原文や個人情報は API から受け取らない・表示しない（NFR-1・NFR-7）。

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getShare, type ShareResult } from "@/lib/api";
import {
  HANDOVER_OPTIONS,
  PREFERENCE_OPTIONS,
  RELATIONSHIP_OPTIONS,
  type ShareResponse,
} from "@/lib/types";
import ProductLink from "./ProductLink";
import ShareViewLogger from "./ShareViewLogger";
import styles from "./page.module.css";

// 値（senior など）→ 画面の日本語ラベル。入力画面と同じ表（lib/types.ts の *_OPTIONS）を使う
function labelOf<T extends string>(options: { value: T; label: string }[], value: T): string {
  return options.find((o) => o.value === value)?.label ?? value;
}

const yen = (n: number) => `${n.toLocaleString("ja-JP")}円`;

// "2026-12-21T09:00:00" → "2026年12月21日"。日時の変換（タイムゾーン）をせず、DB の日付をそのまま見せる
function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[1]}年${Number(m[2])}月${Number(m[3])}日` : iso;
}

// API が止まっているときは例外になるので、「読み込めなかった」として扱う
async function loadShare(shareId: string): Promise<ShareResult | { status: "error" }> {
  try {
    return await getShare(shareId);
  } catch {
    return { status: "error" };
  }
}

// プレビュー（OGP）用の説明文。例：「職場の先輩へ・3人で総予算4,500円・職場で手渡し」
function describe(s: ShareResponse): string {
  return [
    `${labelOf(RELATIONSHIP_OPTIONS, s.relationship)}へ`,
    `${s.num_givers}人で総予算${yen(s.total_budget)}`,
    labelOf(HANDOVER_OPTIONS, s.handover),
  ].join("・");
}

// params は Promise で届く（新しい Next.js の書き方）。page と generateMetadata の両方で await して使う。
// getShare を2回呼んでいるが、同じ URL の fetch は1回の表示の中で Next.js が1回にまとめる（fetch のメモ化）
export async function generateMetadata(
  props: PageProps<"/share/[share_id]">,
): Promise<Metadata> {
  const { share_id } = await props.params;
  const result = await loadShare(share_id);
  if (result.status !== "ok") {
    return { title: "共有ページ｜Giftia" }; // 見つからない・期限切れのときは一般的なタイトル
  }
  const title = `送別ギフトの候補（${result.data.items.length}件）｜Giftia`;
  const description = describe(result.data);
  return {
    title,
    description,
    openGraph: { title, description, type: "website", siteName: "Giftia" },
  };
}

export default async function SharePage(props: PageProps<"/share/[share_id]">) {
  const { share_id } = await props.params;
  const result = await loadShare(share_id);

  // 見つからないときは Next.js の 404 にする（同じフォルダの not-found.tsx が表示される）
  if (result.status === "not_found") notFound();

  if (result.status !== "ok") {
    const message =
      result.status === "expired"
        ? "この共有ページは閲覧期限（発行から30日）が過ぎました。"
        : "共有ページを読み込めませんでした。時間をおいてもう一度お試しください。";
    return (
      <main className={styles.main}>
        <div className={styles.panel}>
          <h1 className={styles.title}>
            {result.status === "expired" ? "閲覧期限が過ぎました" : "読み込めませんでした"}
          </h1>
          <p className={styles.lead}>{message}</p>
        </div>
      </main>
    );
  }

  const s = result.data;
  return (
    <main className={styles.main}>
      <ShareViewLogger shareId={s.share_id} />
      <div className={styles.panel}>
        <h1 className={styles.title}>送別ギフトの候補</h1>
        <p className={styles.lead}>同僚から共有された、外れにくい候補と選んだ理由です。</p>

        {/* 入力条件（要件定義書 4.2：関係性・予算・人数） */}
        <dl className={styles.conditions}>
          <dt>相手</dt>
          <dd>{labelOf(RELATIONSHIP_OPTIONS, s.relationship)}</dd>
          <dt>好みの把握</dt>
          <dd>{labelOf(PREFERENCE_OPTIONS, s.preference_knowledge)}</dd>
          <dt>予算</dt>
          <dd>
            総予算 {yen(s.total_budget)}（{s.num_givers}人・1人あたり {yen(s.per_person_budget)}）
          </dd>
          <dt>渡し方</dt>
          <dd>{labelOf(HANDOVER_OPTIONS, s.handover)}</dd>
        </dl>

        {/* 候補と理由文（共有した時点の内容で固定されている DR-6） */}
        <ol className={styles.items}>
          {s.items.map((item) => (
            <li key={item.rank} className={styles.item}>
              <p className={styles.rank}>{item.rank}位</p>
              <h2 className={styles.name}>{item.product_name}</h2>
              <p className={styles.meta}>
                {item.brand ? `${item.brand}・` : ""}
                {yen(item.price)}
              </p>
              <ul className={styles.reasons}>
                {item.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
              <ProductLink productId={item.product_id} shareId={s.share_id} className={styles.link}>
                商品ページを見る
              </ProductLink>
            </li>
          ))}
        </ol>

        <p className={styles.expires}>閲覧期限：{formatDate(s.expires_at)}まで</p>
      </div>
    </main>
  );
}
