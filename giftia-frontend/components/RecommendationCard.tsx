import type { RecommendationCandidate } from "@/lib/types";
import styles from "./RecommendationCard.module.css";

export default function RecommendationCard({
  candidate,
}: {
  candidate: RecommendationCandidate;
}) {
  return (
    <article className="card">
      <p className={styles.rank}>{candidate.rank}位</p>
      <p className="name">{candidate.product_name}</p>
      <p className="meta">
        {candidate.brand ? `${candidate.brand}／` : ""}
        {candidate.category}
      </p>
      <p className="price">{candidate.price.toLocaleString("ja-JP")}円</p>
      {candidate.delivery_days != null && (
        <p className="meta">配送日数：{candidate.delivery_days}日</p>
      )}

      {candidate.reasons.length > 0 && (
        <ul className={styles.reasons}>
          {candidate.reasons.map((reason, i) => (
            <li key={`${i}-${reason}`} className={styles.reason}>
              {reason}
            </li>
          ))}
        </ul>
      )}

      {candidate.caution && (
        <p className={styles.caution}>注意：{candidate.caution}</p>
      )}
    </article>
  );
}
