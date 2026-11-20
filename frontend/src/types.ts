// Shapes of the backend's /query/stream events and the UI state built from them

export type LaneId = "agent" | "baseline";

export interface SqlItem {
  kind: "sql";
  sql: string;
  ok: boolean;
  rows: number | null;
  truncated: boolean;
  error: string | null;
  blocked: boolean;
  columns: string[];
  sample: string[][];
  tables: string[];
}

export type Item =
  | { kind: "tables_seen"; tables: string[] }
  | { kind: "tables_given"; tables: string[] }
  | { kind: "values"; hits: string[]; count: number }
  | { kind: "note"; text: string }
  | SqlItem;

export interface Step {
  tool: string;
  input: string;
  items: Item[];
}

export interface Lane {
  steps: Step[];
  done: boolean;
  answer?: string | null;
  stop?: string;
  error?: string | null;
  seconds?: number;
  cost?: number;
}

export interface Turn {
  id: number;
  question: string;
  model: string;
  compare: boolean;
  expected: string[];
  lanes: Partial<Record<LaneId, Lane>>;
}

export interface Example {
  group: string;
  question: string;
  profile: string;
  tables: string[];
}

export interface Model {
  id: string;
  label: string;
  short: string;
  note: string;
  local: boolean;
}

export interface Schema {
  tables: { name: string; columns: string[] }[];
  links: { from: string; column: string; to: string; to_column: string }[];
}

// One server-sent event
export type StreamEvent =
  | ({ lane: LaneId; type: "step"; tool: string; input: string })
  | ({ lane: LaneId; type: "tables_seen" | "tables_given"; tables: string[] })
  | ({ lane: LaneId; type: "values"; hits: string[]; count: number })
  | ({ lane: LaneId; type: "note"; text: string })
  | ({ lane: LaneId; type: "sql" } & Omit<SqlItem, "kind">)
  | ({ lane: LaneId; type: "thinking" })
  | ({ lane: LaneId; type: "done"; answer: string | null; stop: string; error: string | null; seconds: number; cost_usd: number })
  | { type: "busy" };
