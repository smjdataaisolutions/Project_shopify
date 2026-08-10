/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { ActionCards } from "../dashboard/ActionNeeded";
import styles from "../dashboard/actionNeeded.module.css";
import {
  downloadSalesActionNeededCsv,
  fetchSalesActionNeeded,
} from "../../services/sales";

export function SalesActionNeeded({ startDate, endDate }) {
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [downloadError, setDownloadError] = useState(null);
  const [downloadingActionId, setDownloadingActionId] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setResponse(null);
    setError(null);
    setDownloadError(null);

    fetchSalesActionNeeded({ startDate, endDate })
      .then((data) => active && setResponse(data))
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message || "Unable to load sales recommendations.",
          );
        }
      });

    return () => {
      active = false;
    };
  }, [startDate, endDate, requestVersion]);

  const downloadRecords = async (action) => {
    setDownloadError(null);
    setDownloadingActionId(action.id);
    try {
      await downloadSalesActionNeededCsv({
        actionId: action.id,
        startDate,
        endDate,
      });
    } catch (requestError) {
      setDownloadError(
        requestError.message || "Unable to download the affected records.",
      );
    } finally {
      setDownloadingActionId(null);
    }
  };

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

  if (!response) {
    return (
      <div className={styles.state}>
        <s-spinner accessibilityLabel="Loading sales recommendations" />
        <s-text>Checking sales performance for issues…</s-text>
      </div>
    );
  }

  if (!response.actions.length) {
    return (
      <div className={styles.state}>
        <s-text>
          {response.has_sufficient_data
            ? "No sales actions require attention for the selected period."
            : "Sales recommendations will appear when sufficient sales data is available."}
        </s-text>
      </div>
    );
  }

  return (
    <>
      {downloadError ? (
        <div className={styles.downloadError}>
          <s-text tone="critical">{downloadError}</s-text>
        </div>
      ) : null}
      <ActionCards
        actions={response.actions}
        onDownload={downloadRecords}
        downloadingActionId={downloadingActionId}
      />
    </>
  );
}
