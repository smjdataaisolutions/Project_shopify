/* eslint-disable react/prop-types */
import { useEffect, useMemo, useRef, useState } from "react";
import { fetchOrderTimeline } from "../../services/orders";
import {
  formatTimelineAmount,
  formatTimelineDate,
  formatTimelineStatus,
  getOrderTimelineState,
  sortOrderTimelineEvents,
} from "../../utils/orderTimeline";
import styles from "./orderTimelineModal.module.css";

const MODAL_ID = "order-performance-timeline-modal";

export function OrderTimelineModal({ order, onClose }) {
  const modalRef = useRef(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const frame = requestAnimationFrame(() => modalRef.current?.showOverlay());
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    let active = true;
    setResult(null);
    setError(null);
    setIsLoading(true);

    fetchOrderTimeline(order.order_id)
      .then((response) => active && setResult(response))
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load this order timeline.");
        }
      })
      .finally(() => active && setIsLoading(false));

    return () => {
      active = false;
    };
  }, [order.order_id, requestVersion]);

  const events = useMemo(
    () => sortOrderTimelineEvents(result?.events),
    [result?.events],
  );
  const viewState = getOrderTimelineState({
    isLoading,
    result,
    error,
    orderId: order.order_id,
  });
  const status = result?.current_status;
  const modalOrderLabel = order.order_name.startsWith("Order ")
    ? order.order_name
    : `Order ${order.order_name}`;

  return (
    <s-modal
      ref={modalRef}
      id={MODAL_ID}
      heading={`${modalOrderLabel} Timeline`}
      accessibilityLabel={`Timeline for order ${order.order_name}`}
      size="base"
      onHide={onClose}
    >
      <div className={styles.content}>
        {viewState === "loading" ? (
          <div className={styles.state}>
            <s-spinner accessibilityLabel={`Loading timeline for ${order.order_name}`} />
            <s-text>Loading order timeline.</s-text>
          </div>
        ) : null}

        {viewState === "error" ? (
          <div className={styles.state}>
            <s-stack direction="block" gap="base" alignItems="center">
              <s-text tone="critical">{error}</s-text>
              <s-button onClick={() => setRequestVersion((value) => value + 1)}>
                Try again
              </s-button>
            </s-stack>
          </div>
        ) : null}

        {viewState === "ready" || viewState === "empty" ? (
          <>
            <div className={styles.statusPanel}>
              <s-text type="strong">Current status</s-text>
              <div className={styles.statusRow}>
                <s-text tone="subdued">Payment status</s-text>
                <s-text>{formatTimelineStatus(status?.payment_status)}</s-text>
              </div>
              <div className={styles.statusRow}>
                <s-text tone="subdued">Fulfilment status</s-text>
                <div>
                  <s-text>{formatTimelineStatus(status?.fulfillment_status)}</s-text>
                  {status?.fulfillment_status &&
                  !status.fulfillment_timestamp_available ? (
                    <div className={styles.eventMeta}>Exact time unavailable</div>
                  ) : null}
                </div>
              </div>
            </div>

            {viewState === "empty" ? (
              <div className={styles.state}>
                <s-text>No timestamped events are available for this order.</s-text>
              </div>
            ) : (
              <div className={styles.timelineScroll}>
                <ol className={styles.timeline} aria-label="Order timeline events">
                  {events.map((event) => (
                    <li
                      className={styles.event}
                      key={`${event.event_type}-${event.occurred_at}`}
                    >
                      <s-text type="strong">{event.title}</s-text>
                      <div className={styles.eventMeta}>
                        {formatTimelineDate(event.occurred_at)}
                      </div>
                      {event.description ? <s-text>{event.description}</s-text> : null}
                      {event.amount != null ? (
                        <s-text>
                          Amount: {formatTimelineAmount(event.amount, result.currency)}
                        </s-text>
                      ) : null}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </>
        ) : null}
      </div>
      <s-button
        slot="secondary-actions"
        commandFor={MODAL_ID}
        command="--hide"
      >
        Close
      </s-button>
    </s-modal>
  );
}
