/* eslint-disable react/prop-types */

/**
 * A small, consistent presentation component for dashboard metrics.
 */
export function KPICard({ label, value }) {
  return (
    <s-box
      padding="base"
      borderWidth="base"
      borderRadius="base"
      background="base"
    >
      <s-stack direction="block" gap="small">
        <s-text tone="subdued">{label}</s-text>
        <s-heading>{value}</s-heading>
      </s-stack>
    </s-box>
  );
}
