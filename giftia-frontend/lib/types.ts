// ============================================================
// FR-1 送別状況の入力（既存の lib/types.ts の末尾に追記する）
// キー名は要件定義書 5.2 share_lists に合わせて snake_case
// ============================================================

export type Relationship = "senior" | "peer" | "boss" | "junior" | "client";
export type PreferenceKnowledge = "low" | "mid" | "high";
export type Handover = "hand" | "ship";

export interface FarewellInput {
  relationship: Relationship;
  preference_knowledge: PreferenceKnowledge;
  total_budget: number; // 円
  num_givers: number; // 人
  handover: Handover;
}

export const RELATIONSHIP_OPTIONS: { value: Relationship; label: string }[] = [
  { value: "senior", label: "職場の先輩" },
  { value: "peer", label: "同僚" },
  { value: "boss", label: "上司" },
  { value: "junior", label: "後輩" },
  { value: "client", label: "取引先" },
];

export const PREFERENCE_OPTIONS: {
  value: PreferenceKnowledge;
  label: string;
}[] = [
  { value: "low", label: "ほとんど知らない" },
  { value: "mid", label: "少し知っている" },
  { value: "high", label: "よく知っている" },
];

export const HANDOVER_OPTIONS: { value: Handover; label: string }[] = [
  { value: "hand", label: "職場で手渡し" },
  { value: "ship", label: "相手に配送" },
];

// 総予算：1,000円刻み。上限は仮置き（班のDBの価格分布を見て確定する）
export const BUDGET_MIN = 1000;
export const BUDGET_MAX = 20000;
export const BUDGET_STEP = 1000;
export const BUDGET_OPTIONS: number[] = Array.from(
  { length: (BUDGET_MAX - BUDGET_MIN) / BUDGET_STEP + 1 },
  (_, i) => BUDGET_MIN + i * BUDGET_STEP,
);

// 贈る人数：1〜10人
export const GIVER_MAX = 10;
export const GIVER_OPTIONS: number[] = Array.from(
  { length: GIVER_MAX },
  (_, i) => i + 1,
);

// 1人あたりの予算（表示用・切り捨て）。backend でも total_budget // num_givers で揃える
export function calcBudgetPerPerson(
  totalBudget: number,
  numGivers: number,
): number {
  return numGivers > 0 ? Math.floor(totalBudget / numGivers) : 0;
}
