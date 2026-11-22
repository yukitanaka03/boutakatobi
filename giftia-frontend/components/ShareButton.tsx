"use client";

// components/ShareButton.tsx — 共有ページを発行して、URL をコピーできるようにするボタン（FR-7）
// 共有手段は LINE に限定しない（案2）。URL をコピーして、チャットやメールなど好きな方法で同僚に送ってもらう。
// 送るのは入力条件だけ。候補と理由はサーバー側で計算し直して保存される。

import { useState } from "react";
import { createShare } from "@/lib/api";
import { logEvent } from "@/lib/events";
import type { ShareInput } from "@/lib/types";
import styles from "./ShareButton.module.css";

type Props = {
  input: ShareInput; // 候補画面で使った入力条件（エピソード原文は含めない）
};

export default function ShareButton({ input }: Props) {
  const [creating, setCreating] = useState(false); // 発行中（二重押しを防ぐ）
  const [url, setUrl] = useState(""); // 発行できた共有ページの URL
  const [error, setError] = useState("");
  const [copyMessage, setCopyMessage] = useState("");

  const handleCreate = async () => {
    if (creating) return;
    setCreating(true);
    setError("");
    setCopyMessage("");
    try {
      const res = await createShare(input);
      // API は画面のオリジン（http://localhost:3000 など）を知らないので、ここでつなげて完全な URL にする
      setUrl(window.location.origin + res.share_path);
      logEvent("share_create", { shareId: res.share_id });
    } catch {
      setError("共有ページを作成できませんでした。時間をおいてもう一度お試しください。");
    } finally {
      setCreating(false);
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopyMessage("URLをコピーしました");
    } catch {
      // http の環境や権限の都合でコピーできないことがある。URL は表示したままにして手で選んでもらう
      setCopyMessage("コピーできませんでした。URLを長押し/選択してコピーしてください");
    }
  };

  return (
    <div className={styles.box}>
      <button
        type="button"
        className={styles.primary}
        onClick={handleCreate}
        disabled={creating}
      >
        {creating ? "作成中…" : "同僚に共有する"}
      </button>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      {url && (
        <div className={styles.result}>
          <p className={styles.note}>
            共有ページを作成しました（閲覧期限は30日です）
          </p>
          {/* 読み取り専用の入力欄に置く：クリックで全体を選べるので、コピーできないときも手で選びやすい */}
          <input
            className={styles.url}
            type="text"
            value={url}
            readOnly
            onFocus={(e) => e.currentTarget.select()}
            aria-label="共有ページのURL"
          />
          <button type="button" className={styles.secondary} onClick={handleCopy}>
            URLをコピー
          </button>
          {copyMessage && (
            <p className={styles.note} role="status">
              {copyMessage}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
