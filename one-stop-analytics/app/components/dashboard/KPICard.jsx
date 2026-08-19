/* eslint-disable react/prop-types */
import styles from "./kpiCard.module.css";

/** A dashboard metric with optional navigation and an accessible formula tooltip. */
export function KPICard({
  id,
  label,
  value,
  supportingText,
  imageUrl,
  imageAlt,
  definition = [],
  onClick,
  accessibilityLabel,
}) {
  const tooltipId = `${id || label.toLowerCase().replaceAll(" ", "-")}-formula`;
  const content = (
    <div className={styles.contentRow}>
      <s-stack direction="block" gap="small">
        <s-text tone="subdued">{label}</s-text>
        <s-heading>{value}</s-heading>
        {supportingText ? <s-text tone="subdued">{supportingText}</s-text> : null}
      </s-stack>
      {imageUrl ? (
        <img className={styles.productImage} src={imageUrl} alt={imageAlt || ""} />
      ) : imageAlt ? (
        <div className={styles.imagePlaceholder} aria-label={`${imageAlt} image unavailable`}>
          No image
        </div>
      ) : null}
    </div>
  );

  return (
    <s-box
      padding="base"
      borderWidth="base"
      borderRadius="base"
      background="base"
    >
      <div className={styles.cardShell}>
        {onClick ? (
          <button
            type="button"
            className={styles.cardButton}
            onClick={onClick}
            aria-label={accessibilityLabel || `Open details for ${label}`}
          >
            {content}
          </button>
        ) : content}

        {definition.length ? (
          <div
            className={`${styles.infoButton} ${imageAlt ? styles.infoButtonWithMedia : ""}`}
          >
            <s-button
              icon="info"
              variant="tertiary"
              accessibilityLabel={`How ${label.toLowerCase()} is calculated`}
              interestFor={tooltipId}
            />
            <s-tooltip id={tooltipId}>
              {definition.map((line) => (
                <s-paragraph key={line}>{line}</s-paragraph>
              ))}
            </s-tooltip>
          </div>
        ) : null}
      </div>
    </s-box>
  );
}
