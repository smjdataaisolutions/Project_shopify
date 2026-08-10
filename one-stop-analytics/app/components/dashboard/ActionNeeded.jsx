/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { fetchActionNeeded } from "../../services/dashboard";
import styles from "./actionNeeded.module.css";

const PRIORITY_PRESENTATION = {
  critical: { label: "Critical", tone: "critical" },
  warning: { label: "Warning", tone: "caution" },
  recommendation: { label: "Recommendation", tone: "info" },
};
const PRODUCT_PREVIEW_LIMIT = 3;

function ActionCard({ action, onDownload, downloadingActionId }) {
  const [showAllProducts, setShowAllProducts] = useState(false);
  const presentation =
    PRIORITY_PRESENTATION[action.priority] ||
    PRIORITY_PRESENTATION.recommendation;
  const affectedProducts = action.affected_products || [];
  const visibleProducts = showAllProducts
    ? affectedProducts
    : affectedProducts.slice(0, PRODUCT_PREVIEW_LIMIT);
  const hasMoreProducts = affectedProducts.length > PRODUCT_PREVIEW_LIMIT;

  return (
    <s-box
      className={styles.card}
      padding="base"
      borderWidth="base"
      borderRadius="base"
      background="base"
    >
      <div className={styles.cardContent}>
        <s-stack direction="block" gap="base">
          <div className={styles.cardHeader}>
            <s-heading>{action.title}</s-heading>
            <s-badge tone={presentation.tone}>{presentation.label}</s-badge>
          </div>
          <s-text>{action.message}</s-text>
          {affectedProducts.length ? (
            <s-stack direction="block" gap="small">
              <s-text>
                <strong>Affected products</strong>
              </s-text>
              <ul className={styles.productList}>
                {visibleProducts.map((product) => (
                  <li key={product.product_id}>
                    {product.product_title} — {product.inventory_quantity}{" "}
                    {product.inventory_quantity === 1 ? "unit" : "units"}
                  </li>
                ))}
              </ul>
              {hasMoreProducts ? (
                <s-button
                  onClick={() => setShowAllProducts((isVisible) => !isVisible)}
                >
                  {showAllProducts ? "Show fewer products" : "View products"}
                </s-button>
              ) : null}
            </s-stack>
          ) : null}
          <s-stack direction="block" gap="small">
            <s-text>
              <strong>Recommended action</strong>
            </s-text>
            <s-text>{action.recommended_action}</s-text>
          </s-stack>
        </s-stack>
        {(action.action_label && action.action_url) ||
        (action.download_available && onDownload) ? (
          <div className={styles.actionFooter}>
            {action.download_available && onDownload ? (
              <s-button
                icon="download"
                variant="tertiary"
                accessibilityLabel={`Download records for ${action.title}`}
                loading={downloadingActionId === action.id}
                onClick={() => onDownload(action)}
              />
            ) : null}
            {action.action_label && action.action_url ? (
              <s-button href={action.action_url} target="_top">
                {action.action_label}
              </s-button>
            ) : null}
          </div>
        ) : null}
      </div>
    </s-box>
  );
}

export function ActionCards({ actions, onDownload, downloadingActionId }) {
  return (
    <div className={styles.grid}>
      {actions.map((action) => (
        <ActionCard
          key={action.id}
          action={action}
          onDownload={onDownload}
          downloadingActionId={downloadingActionId}
        />
      ))}
    </div>
  );
}

export function ActionNeeded({ filters }) {
  const [actions, setActions] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setActions(null);
    setError(null);

    fetchActionNeeded(filters)
      .then((response) => active && setActions(response.actions))
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message || "Unable to load recommended actions.",
          );
        }
      });

    return () => {
      active = false;
    };
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
        <s-text>
          No urgent actions were identified. Your store looks healthy.
        </s-text>
      </div>
    );
  }

  return <ActionCards actions={actions} />;
}
