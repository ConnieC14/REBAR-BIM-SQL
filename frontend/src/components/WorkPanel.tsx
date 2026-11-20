import { useState } from "react";
import type { LaneId, Schema, Turn } from "../types";
import StepList from "./StepList";
import TableMap from "./TableMap";
import { AgentIcon, GraphIcon, LayersIcon, ListIcon } from "./Icons";

interface Props {
  turn: Turn | undefined;
  schema: Schema | null;
  theme: "light" | "dark";
}

export default function WorkPanel({ turn, schema, theme }: Props) {
  const [tab, setTab] = useState<"steps" | "tables">("steps");
  const [laneChoice, setLaneChoice] = useState<LaneId>("agent");
  const lane: LaneId = turn?.compare ? laneChoice : "agent";

  return (
    <section className="panel work">
      <div className="panel-bar">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "steps"} className={tab === "steps" ? "active" : ""}
                  onClick={() => setTab("steps")}><ListIcon size={17} /> Steps</button>
          <button role="tab" aria-selected={tab === "tables"} className={tab === "tables" ? "active" : ""}
                  onClick={() => setTab("tables")}><GraphIcon size={17} /> Tables</button>
        </div>
        {turn?.compare && (
          <div className="segmented small">
            {(["agent", "baseline"] as LaneId[]).map((l) => (
              <button key={l} className={l === lane ? "active" : ""} onClick={() => setLaneChoice(l)}>
                {l === "agent" ? <AgentIcon size={15} /> : <LayersIcon size={15} />}
                {l === "agent" ? "Agent" : "Baseline"}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="work-body">
        {!turn ? (
          <div className="empty">
            <GraphIcon size={44} />
            <span>The agent's steps appear here</span>
          </div>
        ) : tab === "steps" ? (
          <StepList key={`${turn.id}-${lane}`} lane={turn.lanes[lane]} />
        ) : (
          <TableMap key={`${turn.id}-${lane}`} lane={turn.lanes[lane]} schema={schema}
                    expected={turn.expected} theme={theme} />
        )}
      </div>
    </section>
  );
}
