import { Fragment, useState } from "react";
import type { Item, Lane, SqlItem } from "../types";
import { AlertIcon, ArrowRightIcon, CheckIcon, ClockIcon, DatabaseIcon, ListIcon, LockIcon, SpinnerIcon, ToolIcon } from "./Icons";

const LABELS: Record<string, string> = {
  search_schema: "Searched the schema",
  describe_table: "Opened a table",
  find_join_path: "Found how tables connect",
  find_values: "Looked up a value",
  sql_generator: "Asked the database",
  user_proxy: "Searched the schema",
};

const toolKey = (tool: string) => tool.toLowerCase().replace(/ /g, "_");
const label = (tool: string) => LABELS[toolKey(tool)] ?? tool;

// Table names joined by arrows
function TableChain({ tables }: { tables: string[] }) {
  return (
    <div className="chain">
      {tables.map((t, i) => (
        <Fragment key={`${t}-${i}`}>
          {i > 0 && <ArrowRightIcon size={14} />}
          <span className="chain-table">{t}</span>
        </Fragment>
      ))}
    </div>
  );
}

// What the step was given: table names as a chain, anything else quoted
function StepInput({ tool, input }: { tool: string; input: string }) {
  const key = toolKey(tool);
  if (key === "describe_table" || key === "find_join_path") {
    return <TableChain tables={input.split(/[|,]/).map((t) => t.trim()).filter(Boolean)} />;
  }
  return <div className="step-input"><q className="query">{shortInput(tool, input)}</q></div>;
}

// The question part of an SQL Generator input: "Tables | question" on qwen,
// "question | ['Table', ...]" on Claude
function shortInput(tool: string, input: string) {
  if (!tool.toLowerCase().includes("sql") || !input.includes("|")) return input;
  const [first, ...rest] = input.split("|");
  const second = rest.join("|").trim();
  return second.startsWith("[") ? first.trim() : second;
}

function SqlResult({ item }: { item: SqlItem }) {
  const [open, setOpen] = useState(false);
  const tone = item.blocked ? "bad" : item.ok ? "good" : "warn";
  const icon = item.blocked ? <LockIcon size={14} /> : item.ok ? <CheckIcon size={14} /> : <AlertIcon size={14} />;
  const text = item.blocked
    ? "Blocked by the read-only guard"
    : item.ok
      ? `${item.rows ?? 0} ${item.rows === 1 ? "row" : "rows"}${item.truncated ? ", cut off" : ""}`
      : `Error: ${item.error}`;
  return (
    <div className="result">
      <span className={`tag tag-${tone}`}>{icon} {text}</span>
      <button className="link" onClick={() => setOpen(!open)}>{open ? "Hide SQL" : "SQL"}</button>
      {open && (
        <div className="sql">
          <pre>{item.sql}</pre>
          {item.ok && item.columns.length > 0 && (
            <div className="rows-wrap">
              <table className="rows">
                <thead><tr>{item.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>
                  {item.sample.map((row, i) => (
                    <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ItemLine({ item }: { item: Item }) {
  switch (item.kind) {
    case "sql":
      return <SqlResult item={item} />;
    case "tables_seen":
      return <div className="result muted"><TableChain tables={item.tables} /></div>;
    case "tables_given":
      return <div className="result">Using <TableChain tables={item.tables} /></div>;
    case "values":
      return item.count === 0 ? (
        <div className="result"><span className="tag tag-warn"><AlertIcon size={14} /> Not stored as written</span></div>
      ) : (
        <div className="result muted">{item.hits.slice(0, 3).join(" · ")}</div>
      );
    case "note":
      return <div className="result muted">{item.text}</div>;
  }
}

export default function StepList({ lane }: { lane: Lane | undefined }) {
  if (!lane) return null;
  return (
    <div className="steps">
      <ol>
        {lane.steps.map((step, i) => (
          <li key={i} className="step">
            <span className="step-num">{i + 1}</span>
            <span className="step-icon"><ToolIcon tool={step.tool} /></span>
            <div className="step-body">
              <div className="step-title">{label(step.tool)}</div>
              {step.input && <StepInput tool={step.tool} input={step.input} />}
              {step.items.map((item, j) => <div key={j} className="item"><ItemLine item={item} /></div>)}
            </div>
          </li>
        ))}
      </ol>
      {!lane.done && (
        <div className="working">
          <SpinnerIcon size={18} />
          <span>{lane.steps.length === 0 ? "Reading the question" : "Thinking"}</span>
          <span className="dots"><i /><i /><i /></span>
        </div>
      )}
      {lane.done && (
        <div className="totals">
          <span><ListIcon size={16} /> {lane.steps.length} steps</span>
          <span><ClockIcon size={16} /> {lane.seconds?.toFixed(1)} s</span>
          <span><DatabaseIcon size={16} /> {lane.cost ? (lane.cost < 0.01 ? "under 1¢" : `$${lane.cost.toFixed(3)}`) : "free"}</span>
        </div>
      )}
    </div>
  );
}
