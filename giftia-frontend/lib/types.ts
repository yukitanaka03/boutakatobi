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

// ============================================================
// FR-3・4・6 /api/farewell/recommendations の返り値
// backend/schemas.py の Candidate・RecommendationResponse と項目名をそろえる
// ============================================================

export interface RecommendationCandidate {
  rank: number;
  product_id: string;
  product_name: string;
  category: string;
  brand: string | null;
  price: number;
  score: number;
  reasons: string[];
  caution: string | null;
}

export interface RecommendationResponse {
  per_person_budget: number;
  applied_exclusions: string[];
  candidate_count: number;
  episode_used: boolean;
  results: RecommendationCandidate[];
}

// 値（senior など）から日本語ラベル（職場の先輩 など）を引く
export function labelOf(
  options: { value: string; label: string }[],
  value: string,
): string {
  return options.find((o) => o.value === value)?.label ?? value;
}

// URL のクエリを入力条件に戻す。欠けている・不正な値があれば null
export function parseFarewellInput(
  params: Record<string, string | string[] | undefined>,
): FarewellInput | null {
  const get = (key: string) => {
    const v = params[key];
    return typeof v === "string" ? v : "";
  };

  const relationship = get("relationship");
  const preference = get("preference_knowledge");
  const handover = get("handover");
  const totalBudget = Number(get("total_budget"));
  const numGivers = Number(get("num_givers"));

  if (!RELATIONSHIP_OPTIONS.some((o) => o.value === relationship)) return null;
  if (!PREFERENCE_OPTIONS.some((o) => o.value === preference)) return null;
  if (!HANDOVER_OPTIONS.some((o) => o.value === handover)) return null;
  if (!Number.isInteger(totalBudget) || totalBudget <= 0) return null;
  if (!Number.isInteger(numGivers) || numGivers < 1) return null;

  return {
    relationship: relationship as Relationship,
    preference_knowledge: preference as PreferenceKnowledge,
    total_budget: totalBudget,
    num_givers: numGivers,
    handover: handover as Handover,
  };
}

// ============================================================
// FR-7 共有ページ（backend の schemas.py の ShareCreateResponse・ShareItem・ShareResponse と項目名をそろえる）
// 片方だけ変えないこと。日時は JSON では文字列（ISO 形式）で届く
// ============================================================

// 共有ボタンに渡す入力条件。FarewellInput に、テーマ（theme_id だけ。エピソード原文は送らない）と件数を足したもの
export interface ShareInput extends FarewellInput {
  theme_ids?: string[];
  limit?: number; // 3〜5
}

export interface ShareCreateResponse {
  share_id: string;
  share_path: string; // "/share/{share_id}"。画面側で window.location.origin とつなげて完全な URL にする
  expires_at: string; // 閲覧期限（発行から30日）
}

export interface ShareItem {
  rank: number;
  product_id: string;
  product_name: string;
  category: string;
  brand: string | null;
  price: number; // 円
  score: number; // 0〜1
  reasons: string[]; // 共有した時点の理由文
}

export interface ShareResponse {
  share_id: string;
  created_at: string;
  expires_at: string;
  relationship: Relationship;
  preference_knowledge: PreferenceKnowledge;
  total_budget: number;
  num_givers: number;
  per_person_budget: number;
  handover: Handover;
  items: ShareItem[];
}
