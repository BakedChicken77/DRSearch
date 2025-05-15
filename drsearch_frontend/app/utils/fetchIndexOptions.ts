// app\utils\fetchIndexOptions.ts

import { apiBaseUrl } from "./constants";

export interface IndexOption {
  name: string;
  display_name: string;
  example_questions: string[];
}

/**
 * Fetch dropdown choices from the backend.
 * Adds the bearer token when AUTH is enabled.
 */
export async function fetchIndexOptions(token?: string): Promise<IndexOption[]> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const r = await fetch(`${apiBaseUrl}/index-options`, { headers });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(
      `Failed to fetch index options: ${r.status} – ${text || r.statusText}`,
    );
  }
  const data = await r.json();
  if (data.code !== 200 || !Array.isArray(data.result))
    throw new Error("Backend returned malformed data");
  return data.result as IndexOption[];
}