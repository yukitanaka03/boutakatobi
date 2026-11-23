"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  FarewellInput,
  RELATIONSHIP_OPTIONS,
  PREFERENCE_OPTIONS,
  HANDOVER_OPTIONS,
  BUDGET_OPTIONS,
  GIVER_OPTIONS,
  calcBudgetPerPerson,
} from "@/lib/types";
import { logEvent } from "@/lib/events";
import styles from "./FarewellInputForm.module.css";

type FormState = Partial<FarewellInput>;

export default function FarewellInputForm() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>({});

  const update = <K extends keyof FarewellInput>(
    key: K,
    value: FarewellInput[K],
  ) => setForm((prev) => ({ ...prev, [key]: value }));

  const isComplete =
    !!form.relationship &&
    !!form.preference_knowledge &&
    !!form.total_budget &&
    !!form.num_givers &&
    !!form.handover;

  const budgetPerPerson =
    form.total_budget && form.num_givers
      ? calcBudgetPerPerson(form.total_budget, form.num_givers)
      : null;

  const handleSubmit = () => {
    if (!isComplete) return;
    // 1人あたりの予算は表示用のため、クエリには含めない
    const params = new URLSearchParams({
      relationship: form.relationship!,
      preference_knowledge: form.preference_knowledge!,
      total_budget: String(form.total_budget),
      num_givers: String(form.num_givers),
      handover: form.handover!,
    });
    logEvent("input_submit");
    // 次はエピソード入力（任意）。テーマを読み取ってから候補へ進む（FR-2）
    router.push(`/farewell/episode?${params.toString()}`);
  };

  return (
    <div className={styles.form}>
      <label className={styles.field}>
        <span className={styles.label}>相手との関係性</span>
        <select
          className={styles.select}
          defaultValue=""
          onChange={(e) =>
            update(
              "relationship",
              e.target.value as FarewellInput["relationship"],
            )
          }
        >
          <option value="" disabled>
            選択してください
          </option>
          {RELATIONSHIP_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <label className={styles.field}>
        <span className={styles.label}>
          相手の好みをどれくらい知っていますか
        </span>
        <select
          className={styles.select}
          defaultValue=""
          onChange={(e) =>
            update(
              "preference_knowledge",
              e.target.value as FarewellInput["preference_knowledge"],
            )
          }
        >
          <option value="" disabled>
            選択してください
          </option>
          {PREFERENCE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <div className={styles.row}>
        <label className={styles.field}>
          <span className={styles.label}>総予算</span>
          <select
            className={styles.select}
            defaultValue=""
            onChange={(e) => update("total_budget", Number(e.target.value))}
          >
            <option value="" disabled>
              選択してください
            </option>
            {BUDGET_OPTIONS.map((b) => (
              <option key={b} value={b}>
                {b.toLocaleString()}円
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.label}>贈る人数</span>
          <select
            className={styles.select}
            defaultValue=""
            onChange={(e) => update("num_givers", Number(e.target.value))}
          >
            <option value="" disabled>
              選択してください
            </option>
            {GIVER_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}人
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={styles.perPerson} aria-live="polite">
        <span className={styles.perPersonLabel}>1人あたりの予算</span>
        <span className={styles.perPersonValue}>
          {budgetPerPerson !== null
            ? `${budgetPerPerson.toLocaleString()}円`
            : "—"}
        </span>
      </div>

      <label className={styles.field}>
        <span className={styles.label}>渡し方</span>
        <select
          className={styles.select}
          defaultValue=""
          onChange={(e) =>
            update("handover", e.target.value as FarewellInput["handover"])
          }
        >
          <option value="" disabled>
            選択してください
          </option>
          {HANDOVER_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={!isComplete}
        className={styles.button}
      >
        次へ
      </button>
      {!isComplete && (
        <p className={styles.hint}>5つの項目をすべて選ぶと次へ進めます</p>
      )}
    </div>
  );
}
