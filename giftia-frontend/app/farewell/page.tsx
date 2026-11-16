import FarewellInputForm from "@/components/FarewellInputForm";
import styles from "./page.module.css";

export default function FarewellPage() {
  return (
    <main className={styles.main}>
      <div className={styles.panel}>
        <h1 className={styles.title}>送別の贈り物を選ぶ</h1>
        <p className={styles.lead}>
          相手との関係や予算を選ぶと、外れにくい候補を理由つきで提案します。
        </p>
        <FarewellInputForm />
      </div>
    </main>
  );
}
