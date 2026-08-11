export async function downloadCsv(endpoint, fallbackFilename) {
  const response = await fetch(endpoint, {
    headers: { Accept: "text/csv" },
  });
  if (!response.ok) {
    throw new Error(`CSV download request failed (${response.status}).`);
  }

  const disposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  const filename = filenameMatch?.[1] || fallbackFilename;
  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
