// app/FarewellHero.tsx — TOPの「だからコレ。」紹介エリア（/farewell への入口）
// Phase1 は送別のみ対応。他のシーンは「準備中」として表示だけする（要件定義書2章）
import Link from "next/link";
import styles from "./FarewellHero.module.css";

const SCENES = [
  { label: "送別", available: true },
  { label: "取引先へのお礼", available: false },
  { label: "家族への誕生日", available: false },
];

const STEPS = [
  { no: "1", title: "状況を選ぶ", text: "関係性・予算・人数・渡し方" },
  {
    no: "2",
    title: "エピソードを書く（任意）",
    text: "「毎日コーヒーを飲んでいる」など",
  },
  {
    no: "3",
    title: "理由つきの候補を見る",
    text: "外れにくい5点を理由と一緒に",
  },
];

export default function FarewellHero() {
  return (
    <section className={styles.hero} aria-labelledby="farewell-hero-title">
      <div className={styles.copy}>
        <p className={styles.nameRow}>
          <span className={styles.badge}>NEW</span>
          <span className={styles.name}>だからコレ。</span>
          <span className={styles.subName}>｜理由つきギフト選び</span>
        </p>

        <h2 id="farewell-hero-title" className={styles.title}>
          <span className={styles.titleLine}>好みがわからない相手への</span>
          <span className={styles.titleLine}>ギフト、外さずに選べる</span>
        </h2>

        <p className={styles.lead}>
          <span className={styles.leadLine}>
            関係性・予算・人数を選ぶだけ。
          </span>
          <span className={styles.leadLine}>
            外れにくい候補5点と「選んだ理由」をお届けします。
          </span>
        </p>

        <div className={styles.scenes}>
          <p className={styles.scenesLabel}>シーン</p>
          <ul className={styles.sceneList}>
            {SCENES.map((s) => (
              <li
                key={s.label}
                className={s.available ? styles.sceneOn : styles.sceneOff}
              >
                {s.available && <span aria-hidden="true">✓ </span>}
                {s.label}
                {s.available ? (
                  <span className={styles.srOnly}>（選択中）</span>
                ) : (
                  <span className={styles.soon}>準備中</span>
                )}
              </li>
            ))}
          </ul>
        </div>

        <Link href="/farewell" className={styles.cta}>
          「だからコレ。」で選ぶ →
        </Link>
      </div>

      {/* 結果の見本：「理由が出る」ことを一目で伝える */}
      <div className={styles.sample}>
        <p className={styles.sampleLabel}>表示イメージ</p>
        <p className={styles.sampleRank}>1位</p>
        <p className={styles.sampleName}>国産タオルギフトセット</p>
        <p className={styles.sampleReasonTitle}>だからコレ。</p>
        <ul className={styles.chips}>
          <li className={styles.chip}>香りなし・好みに左右されにくい</li>
          <li className={styles.chip}>送別で選ばれている</li>
        </ul>
      </div>

      <ol className={styles.steps}>
        {STEPS.map((s) => (
          <li key={s.no} className={styles.step}>
            <span className={styles.stepNo}>{s.no}</span>
            <div>
              <p className={styles.stepTitle}>{s.title}</p>
              <p className={styles.stepText}>{s.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
