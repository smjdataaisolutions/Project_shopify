export function getDailyStorePerformanceState({ isLoading, result, error }) {
  if (isLoading && !result) return "loading";
  if (error) return "error";
  if (!result?.items?.length) return "empty";
  return "ready";
}
