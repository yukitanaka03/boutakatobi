"use client";

// FR-2 エピソード入力の部品
// 入力した文章はこの画面の中（state）だけで持ち、URL・ブラウザの保存領域・ログには残さない（NFR-1）。
// 候補画面へ渡すのは、読み取ったテーマID（T001 など）だけ。

import { useState } from "react";
import { useRouter } from "next/navigation";
import { extractThemes } from "@/lib/api";
import { logEvent } from "@/lib/events";
import { toFarewellQuery, type FarewellInput, type Theme } from "@/lib/types";
import styles from "./episode.module.css";

const MAX_LENGTH = 300; // backend の ThemeRequest（max_length=300）とそろえる

// idle=未読み取り / loading=読み取り中 / done=読み取れた / empty=手がかりなし・失敗
type Status = "idle" | "loading" | "done" | "empty";

export default function EpisodeForm({ input }: { input: FarewellInput }) {
  const router = useRouter();
  const [episode, setEpisode] = useState("");
  const [themes, setThemes] = useState<Theme[]>([]);
  const [status, setStatus] = useState<Status>("idle");

  // 文章を書き換えたら、前に読み取ったテーマは使わない（文章と食い違うため）
  const onChange = (value: string) => {
    setEpisode(value);
    if (status !== "idle") {
      setThemes([]);
      setStatus("idle");
    }
  };

  const onRead = async () => {
    if (!episode.trim()) return;
    setStatus("loading");
    try {
      const res = await extractThemes(episode);
      if (res.extracted && res.themes.length > 0) {
        setThemes(res.themes);
        setStatus("done");
      } else {
        setThemes([]);
        setStatus("empty");
      }
    } catch {
      // 原文が混ざらないよう、文章は出さずに失敗したことだけ残す
      console.warn("テーマを読み取れませんでした");
      setThemes([]);
      setStatus("empty");
    }
  };

  const removeTheme = (themeId: string) =>
    setThemes((prev) => prev.filter((t) => t.theme_id !== themeId));

  // 候補画面へ進む。テーマがあれば URL に theme_ids として足す
  const goResults = (themeIds: string[]) => {
    if (themeIds.length > 0) logEvent("episode_submit");
    router.push(
      `/farewell/results?${toFarewellQuery({ ...input, theme_ids: themeIds })}`,
    );
  };

  return (
    <div className={styles.form}>
      <label className={styles.field}>
        <span className={styles.label}>エピソードや伝えたいこと</span>
        <textarea
          className={styles.textarea}
          value={episode}
          maxLength={MAX_LENGTH}
          rows={5}
          placeholder="例：デスクにいつもマグカップがあって、毎日コーヒーを飲んでいる"
          onChange={(e) => onChange(e.target.value)}
        />
        <span className={styles.counter}>
          {episode.length}／{MAX_LENGTH}字
        </span>
      </label>

      <ul className={styles.notes}>
        <li>入力した文章は保存されません。読み取った内容だけを使います。</li>
        <li>相手の氏名や、個人的な事情は書かないでください。</li>
      </ul>

      <button
        type="button"
        className={styles.secondary}
        onClick={onRead}
        disabled={!episode.trim() || status === "loading"}
      >
        {status === "loading" ? "読み取り中…" : "内容を読み取る"}
      </button>

      {status === "done" && (
        <div className={styles.result} aria-live="polite">
          <p className={styles.resultLabel}>
            読み取った内容（違うものは × で外せます）
          </p>
          {themes.length > 0 ? (
            <ul className={styles.chips}>
              {themes.map((t) => (
                <li key={t.theme_id} className={styles.chip}>
                  {t.name}
                  <button
                    type="button"
                    className={styles.chipRemove}
                    aria-label={`${t.name}を外す`}
                    onClick={() => removeTheme(t.theme_id)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.message}>
              内容をすべて外しました。エピソードなしで候補を出します。
            </p>
          )}
        </div>
      )}

      {status === "empty" && (
        <p className={styles.message} aria-live="polite">
          内容を読み取れませんでした。エピソードなしで候補を出します。
        </p>
      )}

      {status === "done" && themes.length > 0 && (
        <button
          type="button"
          className={styles.primary}
          onClick={() => goResults(themes.map((t) => t.theme_id))}
        >
          この内容で候補を見る
        </button>
      )}

      <button
        type="button"
        className={
          status === "done" && themes.length > 0 ? styles.skip : styles.primary
        }
        onClick={() => goResults([])}
        disabled={status === "loading"}
      >
        {status === "idle" || status === "loading"
          ? "スキップして候補を見る"
          : "エピソードなしで候補を見る"}
      </button>
    </div>
  );
}
