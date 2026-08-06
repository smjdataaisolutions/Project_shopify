/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { fetchBusinessHighlights } from "../../services/dashboard";
import styles from "./businessHighlights.module.css";

const SEVERITY_PRESENTATION = {
  positive: { label: "Healthy", tone: "success" },
  info: { label: "Information", tone: "info" },
  warning: { label: "Needs attention", tone: "caution" },
  critical: { label: "Critical", tone: "critical" },
};

function HighlightCard({ highlight }) {
  const presentation = SEVERITY_PRESENTATION[highlight.severity]
    || SEVERITY_PRESENTATION.info;

  return (
    <s-box
      padding="base"
      borderWidth="base"
      borderRadius="base"
      background="base"
    >
      <s-stack direction="block" gap="base">
        <div className={styles.cardHeader}>
          <s-heading>{highlight.title}</s-heading>
          <s-badge tone={presentation.tone}>{presentation.label}</s-badge>
        </div>
        <s-text>{highlight.message}</s-text>
        {highlight.supporting_text ? (
          <s-text tone="subdued">{highlight.supporting_text}</s-text>
        ) : null}
      </s-stack>
    </s-box>
  );
}

export function BusinessHighlights({ filters }) {
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
      <div className={styles.state}>
        <s-spinner accessibilityLabel="Loading business highlights" />
        <s-text>Generating business highlights…</s-text>
      </div>
    );
  }

  if (!highlights.length) {
    return (
      <div className={styles.state}>
        <s-text>
          Business highlights will appear when sufficient sales, inventory,
          and product data is available.
        </s-text>
      </div>
    );
  }

  return (
    <div className={styles.grid}>
      {highlights.map((highlight) => (
        <HighlightCard key={highlight.id} highlight={highlight} />
      ))}
    </div>
  );
}
