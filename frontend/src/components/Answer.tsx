import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Lane } from "../types";
import { AgentIcon, AlertIcon, ClockIcon, DatabaseIcon, LayersIcon, LockIcon, XIcon } from "./Icons";

// One-line verdict on how the answer was produced
function Status({ lane }: { lane: Lane }) {
  const queries = lane.steps.flatMap((s) => s.items).filter((i) => i.kind === "sql");
  if (lane.stop === "error") return <span className="tag tag-bad"><XIcon size={14} /> {lane.error}</span>;
  if (lane.stop === "step_limit") return <span className="tag tag-warn"><ClockIcon size={14} /> Ran out of steps</span>;
  if (queries.some((q) => q.kind === "sql" && q.blocked))
    return <span className="tag tag-bad"><LockIcon size={14} /> Write blocked</span>;
  if (!queries.some((q) => q.kind === "sql" && q.ok))
    return <span className="tag tag-warn"><AlertIcon size={14} /> No database query</span>;
  return <span className="tag tag-neutral"><DatabaseIcon size={14} /> From a database query</span>;
}

export default function Answer({ lane, label }: { lane: Lane | undefined; label?: "agent" | "baseline" }) {
  return (
    <div className="answer">
      {label && (
        <div className="answer-label">
          {label === "agent" ? <AgentIcon size={15} /> : <LayersIcon size={15} />}
          {label === "agent" ? "REBAR agent" : "Baseline"}
        </div>
      )}
      {!lane || !lane.done ? (
        <div className="skeleton" aria-label="Working">
          <span /><span /><span />
        </div>
      ) : (
        <div className="answer-done">
          {lane.answer && (
            <div className="markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{lane.answer}</ReactMarkdown>
            </div>
          )}
          <Status lane={lane} />
        </div>
      )}
    </div>
  );
}
