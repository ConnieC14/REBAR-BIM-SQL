import type { Example, Model, Schema, StreamEvent } from "./types";

// Same host as the page, so the demo also works from another device on the network
export const API = `http://${window.location.hostname}:8000`;

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

export const getModels = () =>
  getJson<{ default_model: string; models: Model[] }>("/");
export const getSchema = () => getJson<Schema>("/schema");
export const getExamples = () => getJson<Example[]>("/examples");

export async function streamQuery(
  body: { question: string; model: string; compare: boolean; profile: string },
  onEvent: (event: StreamEvent) => void,
) {
  const res = await fetch(`${API}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)));
    }
  }
}
