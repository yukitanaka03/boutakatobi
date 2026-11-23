// FR-2 エピソード入力（/farewell/episode）
// 状況入力の条件を URL から受け取り、エピソード入力の部品（EpisodeForm）に渡す。
// 条件の受け取り方は候補画面（results/page.tsx）とそろえる。
import Link from "next/link";
import { parseFarewellInput } from "@/lib/types";
import EpisodeForm from "./EpisodeForm";
import styles from "./episode.module.css";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function FarewellEpisodePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  // URL の条件を読み取る。欠けていれば入力画面へ戻す（候補画面と同じ扱い）
  const input = parseFarewellInput(await searchParams);
  if (!input) {
    return (
      <main className={styles.main}>
        <div className={styles.panel}>
          <h1 className={styles.title}>条件が不足しています</h1>
          <p className={styles.lead}>入力画面から条件を選び直してください。</p>
          <Link href="/farewell" className={styles.back}>
            条件を選び直す
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className={styles.main}>
      <div className={styles.panel}>
        <Link href="/farewell" className={styles.backTop}>
          ← 条件を選び直す
        </Link>
        <h1 className={styles.title}>相手とのエピソード（任意）</h1>
        <p className={styles.lead}>
          相手の趣味や習慣が分かるエピソードがあれば書いてください。
          <br />
          内容を読み取って、候補の順位に反映します。
        </p>
        <EpisodeForm input={input} />
      </div>
    </main>
  );
}
