import type { Item, Lane, Step, StreamEvent, Turn } from "./types";

export const emptyLane = (): Lane => ({ steps: [], done: false });

// Applies one streamed event to a turn (returns a new turn)
export function applyEvent(turn: Turn, event: StreamEvent): Turn {
  if (event.type === "busy" || event.type === "thinking") return turn;
  const lane = turn.lanes[event.lane] ?? emptyLane();
  let steps: Step[] = lane.steps;
  let next: Lane;

  if (event.type === "done") {
    next = { ...lane, done: true, answer: event.answer, stop: event.stop, error: event.error,
             seconds: event.seconds, cost: event.cost_usd };
  } else if (event.type === "step") {
    next = { ...lane, steps: [...steps, { tool: event.tool, input: event.input, items: [] }] };
  } else {
    const item: Item =
      event.type === "sql"
        ? { kind: "sql", sql: event.sql, ok: event.ok, rows: event.rows, truncated: event.truncated,
            error: event.error, blocked: event.blocked, columns: event.columns, sample: event.sample,
            tables: event.tables }
        : event.type === "values"
          ? { kind: "values", hits: event.hits, count: event.count }
          : event.type === "note"
            ? { kind: "note", text: event.text }
            : { kind: event.type, tables: event.tables };
    if (steps.length === 0) steps = [{ tool: "sql_generator", input: "", items: [] }];
    const last = steps[steps.length - 1];
    next = { ...lane, steps: [...steps.slice(0, -1), { ...last, items: [...last.items, item] }] };
  }
  return { ...turn, lanes: { ...turn.lanes, [event.lane]: next } };
}

// How far each table got in a lane: 3 queried, 2 given to the SQL writer, 1 opened, 0 seen
export interface TableUse {
  level: number;
  steps: number[];
}

export function tableUse(lane: Lane | undefined, known: Set<string>): Map<string, TableUse> {
  const use = new Map<string, TableUse>();
  const mark = (table: string, level: number, step: number) => {
    const name = [...known].find((k) => k.toLowerCase() === table.trim().toLowerCase());
    if (!name) return;
    const current = use.get(name) ?? { level: -1, steps: [] };
    use.set(name, {
      level: Math.max(current.level, level),
      steps: current.steps.includes(step) ? current.steps : [...current.steps, step],
    });
  };
  lane?.steps.forEach((step, index) => {
    const n = index + 1;
    const tool = step.tool.toLowerCase().replace(/ /g, "_");
    if (tool === "describe_table") mark(step.input, 1, n);
    if (tool === "find_join_path") step.input.split(/[,|]/).forEach((t) => mark(t, 1, n));
    for (const item of step.items) {
      if (item.kind === "tables_seen") item.tables.forEach((t) => mark(t, 0, n));
      if (item.kind === "values") item.hits.forEach((h) => mark(h.split(".")[0], 0, n));
      if (item.kind === "tables_given") item.tables.forEach((t) => mark(t, 2, n));
      if (item.kind === "sql") item.tables.forEach((t) => mark(t, 3, n));
    }
  });
  return use;
}
