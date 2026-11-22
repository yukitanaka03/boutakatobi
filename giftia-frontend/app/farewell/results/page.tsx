import Link from "next/link";
import RecommendationCard from "@/components/RecommendationCard";
import { fetchRecommendations } from "@/lib/api";
import {
  parseFarewellInput,
  labelOf,
  calcBudgetPerPerson,
  RELATIONSHIP_OPTIONS,
  PREFERENCE_OPTIONS,
  HANDOVER_OPTIONS,
} from "@/lib/types";
import type { RecommendationResponse } from "@/lib/types";
import styles from "./results.module.css";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

// API の除外条件（「理由：外したもの」の形）を、理由ごとに一文にまとめる
// 例：好みをほとんど知らないため、好みへの依存度が高い商品と香りが強い商品を外しました。
function describeExclusions(exclusions: string[]): string {
  const groups = new Map<string, string[]>();
  for (const text of exclusions) {
    const i = text.search(/[：:]/);
    const reason = i >= 0 ? text.slice(0, i) : "";
    const item = i >= 0 ? text.slice(i + 1) : text;
    groups.set(reason, [...(groups.get(reason) ?? []), item]);
  }

  // 「A」「AとB」「A、BとC」の形にする
  const joinItems = (items: string[]) =>
    items.length <= 1
      ? items.join("")
      : `${items.slice(0, -1).join("、")}と${items[items.length - 1]}`;

  // 「知らない」「ある」などは「ため」、「手渡し」などの名詞は「のため」でつなぐ
  const because = (reason: string) =>
    /[いるた]$/.test(reason) ? `${reason}ため、` : `${reason}のため、`;

  return Array.from(
    groups,
    ([reason, items]) =>
      `${reason ? because(reason) : ""}${joinItems(items)}を外しました。`,
  ).join("");
}

// 条件不足・API停止・0件のときに出す画面
function Message({ title, body }: { title: string; body: string }) {
  return (
    <main className={styles.main}>
      <div className={styles.panel}>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.lead}>{body}</p>
        <Link href="/farewell" className={styles.back}>
          条件を選び直す
        </Link>
      </div>
    </main>
  );
}

export default async function FarewellResultsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  // ① URL の条件を読み取る。欠けていれば入力画面へ戻す
  const input = parseFarewellInput(await searchParams);
  if (!input) {
    return (
      <Message
        title="条件が不足しています"
        body="入力画面から条件を選び直してください。"
      />
    );
  }

  // ② API に候補を聞く。失敗したらエラー表示
  let data: RecommendationResponse | null = null;
  try {
    data = await fetchRecommendations(input);
  } catch (err) {
    console.error("fetchRecommendations failed:", err);
    data = null;
  }
  if (!data) {
    return (
      <Message
        title="候補を取得できませんでした"
        body="時間をおいて再度お試しください。"
      />
    );
  }

  // ③ 0件なら条件の見直しを促す
  if (data.results.length === 0) {
    return (
      <Message
        title="条件に合う候補が見つかりませんでした"
        body="総予算や渡し方を変えて、もう一度お試しください。"
      />
    );
  }

  // ④ 候補を表示する
  const perPerson = calcBudgetPerPerson(input.total_budget, input.num_givers);

  return (
    <main className={styles.main}>
      <div className={styles.panel}>
        <h1 className={styles.title}>おすすめの送別ギフト</h1>

        <dl className={styles.summary}>
          <div>
            <dt>相手</dt>
            <dd>{labelOf(RELATIONSHIP_OPTIONS, input.relationship)}</dd>
          </div>
          <div>
            <dt>好み</dt>
            <dd>{labelOf(PREFERENCE_OPTIONS, input.preference_knowledge)}</dd>
          </div>
          <div>
            <dt>総予算</dt>
            <dd>
              {input.total_budget.toLocaleString("ja-JP")}円（{input.num_givers}
              人・1人あたり
              {perPerson.toLocaleString("ja-JP")}円）
            </dd>
          </div>
          <div>
            <dt>渡し方</dt>
            <dd>{labelOf(HANDOVER_OPTIONS, input.handover)}</dd>
          </div>
        </dl>

        {data.applied_exclusions.length > 0 && (
          <p className={styles.exclusions}>
            {describeExclusions(data.applied_exclusions)}
          </p>
        )}

        <div className="grid">
          {data.results.map((c) => (
            <RecommendationCard key={c.product_id} candidate={c} />
          ))}
        </div>

        <Link href="/farewell" className={styles.back}>
          条件を変えて選び直す
        </Link>
      </div>
    </main>
  );
}
