import Link from "next/link";
import FarewellInputForm from "@/components/FarewellInputForm";
import styles from "./page.module.css";

export default function FarewellPage() {
  return (
    <main className={styles.main}>
      <div className={styles.panel}>
        <Link href="/" className={styles.backTop}>
          ← Giftiaのトップへ戻る
        </Link>
        <h1 className={styles.title}>送別ギフトを選ぶ</h1>
        <p className={styles.lead}>
          相手との関係や予算を選ぶと、おすすめギフトを理由つきで提案します。
        </p>
        <FarewellInputForm />
      </div>
    </main>
  );
}
