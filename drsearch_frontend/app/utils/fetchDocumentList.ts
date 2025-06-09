// app\utils\fetchDocumentList.ts

import { apiBaseUrl } from "./constants";

/**
 * Fetch list of documents for a given index.
 */
export async function fetchDocumentList(
  index: string,
  token?: string,
): Promise<string[]> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const r = await fetch(
    `${apiBaseUrl}/documents?index=${encodeURIComponent(index)}`,
    {
      headers,
    },
  );
  if (!r.ok) {
    const text = await r.text();
    throw new Error(
      `Failed to fetch document list: ${r.status} – ${text || r.statusText}`,
    );
  }
  const data = await r.json();
  if (data.code !== 200 || !Array.isArray(data.result))
    throw new Error("Backend returned malformed data");
  return data.result as string[];
}
