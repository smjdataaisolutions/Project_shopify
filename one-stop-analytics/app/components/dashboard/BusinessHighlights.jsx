/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { fetchBusinessHighlights } from "../../services/dashboard";
import {
  getHighlightDestination,
  getHighlightPresentation,
} from "../../utils/businessHighlights";
import styles from "./businessHighlights.module.css";

function HighlightCard({ highlight, onViewDailyPerformance }) {
  const navigate = useNavigate();
  const presentation = getHighlightPresentation(highlight.status);
  const handleAction = () => {
    if (highlight.id === "sales_momentum") {
      onViewDailyPerformance();
      return;
    }
    const destination = getHighlightDestination(highlight.id);
    if (destination) navigate(destination);
  };

  return (
    <s-box
      padding="base"
      borderWidth="base"
      borderRadius="base"
      background="base"
    >
      <div className={styles.cardContent}>
        <div className={styles.cardHeader}>
          <s-heading>{highlight.title}</s-heading>
          <s-badge tone={presentation.tone}>{presentation.label}</s-badge>
        </div>
        <s-text>{highlight.message}</s-text>
        {highlight.supporting_text ? (
          <s-text tone="subdued">{highlight.supporting_text}</s-text>
        ) : null}
        {highlight.helper_text ? (
          <s-text tone="subdued">{highlight.helper_text}</s-text>
        ) : null}
        <div className={styles.action}>
          <s-button onClick={handleAction}>{highlight.action_label}</s-button>
        </div>
      </div>
    </s-box>
  );
}

export function BusinessHighlights({ filters, onViewDailyPerformance }) {
  const [highlights, setHighlights] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setHighlights(null);
    setError(null);

    fetchBusinessHighlights(filters)
      .then((response) => active && setHighlights(response.highlights))
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load business highlights.");
        }
      });

    return () => { active = false; };
  }, [filters, requestVersion]);

  if (error) {
    return (
      <div className={styles.state}>
        <s-stack direction="block" gap="base" alignItems="center">
          <s-text tone="critical">{error}</s-text>
          <s-button onClick={() => setRequestVersion((version) => version + 1)}>
            Try again
          </s-button>
        </s-stack>
      </div>
    );
  }

  if (!highlights) {
    return (
      <div className={styles.grid} aria-label="Loading business highlights">
        {[0, 1, 2].map((index) => (
          <div className={styles.loadingCard} key={index}>
            <s-spinner accessibilityLabel="Loading business highlight" />
            <s-text>Generating insight…</s-text>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={styles.grid}>
      {highlights.map((highlight) => (
        <HighlightCard
          key={highlight.id}
          highlight={highlight}
          onViewDailyPerformance={onViewDailyPerformance}
        />
      ))}
    </div>
  );
}
