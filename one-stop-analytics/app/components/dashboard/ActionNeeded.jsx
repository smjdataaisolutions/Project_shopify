/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { fetchActionNeeded } from "../../services/dashboard";
import styles from "./actionNeeded.module.css";

const PRIORITY_PRESENTATION = {
  critical: { label: "Critical", tone: "critical" },
  warning: { label: "Warning", tone: "caution" },
  recommendation: { label: "Recommendation", tone: "info" },
};

function ActionCard({ action }) {
  const presentation = PRIORITY_PRESENTATION[action.priority]
    || PRIORITY_PRESENTATION.recommendation;

  return (
    <s-box
      padding="base"
      borderWidth="base"
      borderRadius="base"
      background="base"
    >
      <s-stack direction="block" gap="base">
        <div className={styles.cardHeader}>
          <s-heading>{action.title}</s-heading>
          <s-badge tone={presentation.tone}>{presentation.label}</s-badge>
        </div>
        <s-text>{action.message}</s-text>
        <s-stack direction="block" gap="small">
          <s-text type="strong">Recommended action</s-text>
          <s-text type="strong">{action.recommended_action}</s-text>
        </s-stack>
      </s-stack>
    </s-box>
  );
}

export function ActionNeeded() {
  const [actions, setActions] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setActions(null);
    setError(null);

    fetchActionNeeded()
      .then((response) => active && setActions(response.actions))
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load recommended actions.");
        }
      });

    return () => { active = false; };
  }, [requestVersion]);

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

  if (!actions) {
    return (
      <div className={styles.state}>
        <s-spinner accessibilityLabel="Loading recommended actions" />
        <s-text>Checking your store for issues…</s-text>
      </div>
    );
  }

  if (!actions.length) {
    return (
      <div className={styles.state}>
        <s-text>No urgent actions were identified. Your store looks healthy.</s-text>
      </div>
    );
  }

  return (
    <div className={styles.grid}>
      {actions.map((action) => (
        <ActionCard key={action.id} action={action} />
      ))}
    </div>
  );
}
