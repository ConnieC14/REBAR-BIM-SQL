import { useMemo, useState } from "react";
import { ReactFlow, Background, Controls, Handle, MarkerType, Position, type Edge, type Node, type NodeProps } from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import type { Lane, Schema } from "../types";
import { tableUse } from "../state";
import { CheckIcon, TableIcon } from "./Icons";

const LEVELS = ["Seen in search", "Opened", "Given to SQL writer", "Queried"];
const NODE_W = 190;
const NODE_H = 50;

type TableData = { name: string; level: number; expected: boolean; missed: boolean };

function TableNode({ data, selected }: NodeProps<Node<TableData>>) {
  const cls = data.missed ? "missed" : `lvl-${data.level}`;
  // Keyed by level, so the node pops each time the agent gets further with it
  return (
    <div key={data.level} className={`tnode ${cls} ${selected ? "sel" : ""}`}>
      <Handle type="target" position={Position.Top} />
      <TableIcon size={16} />
      <span className="tnode-name">{data.name}</span>
      {data.expected && !data.missed && (
        <span className="tnode-exp" title="Needed for this question"><CheckIcon size={16} /></span>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

const nodeTypes = { table: TableNode };

function layout(nodes: Node<TableData>[], edges: Edge[]) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 28, ranksep: 56 });
  g.setDefaultEdgeLabel(() => ({}));
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id);
    return { ...n, position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 } };
  });
}

interface Props {
  lane: Lane | undefined;
  schema: Schema | null;
  expected: string[];
  theme: "light" | "dark";
}

export default function TableMap({ lane, schema, expected, theme }: Props) {
  const [showSeen, setShowSeen] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const known = useMemo(() => new Set(schema?.tables.map((t) => t.name) ?? []), [schema]);
  const use = useMemo(() => tableUse(lane, known), [lane, known]);

  const { nodes, edges } = useMemo(() => {
    const names = new Set([...use].filter(([, u]) => showSeen || u.level >= 1).map(([t]) => t));
    expected.forEach((t) => names.add(t));
    const nodes: Node<TableData>[] = [...names].map((name) => {
      const level = use.get(name)?.level ?? -1;
      const isExpected = expected.includes(name);
      return { id: name, type: "table", position: { x: 0, y: 0 },
               data: { name, level, expected: isExpected, missed: isExpected && level < 2 } };
    });
    const seen = new Set<string>();
    const edges: Edge[] = [];
    for (const link of schema?.links ?? []) {
      const key = [link.from, link.to].sort().join("|");
      if (!names.has(link.from) || !names.has(link.to) || link.from === link.to || seen.has(key)) continue;
      seen.add(key);
      const active = picked === link.from || picked === link.to;
      // Arrow from the table holding the key to the table it points to
      edges.push({ id: key, source: link.from, target: link.to, className: active ? "active" : "",
                   markerEnd: { type: MarkerType.ArrowClosed, width: 22, height: 22,
                                color: active ? "var(--accent)" : "var(--muted)" },
                   label: active ? `${link.from}.${link.column} → ${link.to}` : undefined });
    }
    return { nodes: layout(nodes, edges), edges };
  }, [use, expected, schema, showSeen, picked]);

  const detail = picked ? schema?.tables.find((t) => t.name === picked) : null;
  const pickedUse = picked ? use.get(picked) : undefined;

  if (!lane) return null;
  return (
    <div className="tablemap">
      <div className="legend">
        {LEVELS.map((l, i) => (i > 0 || showSeen) && <span key={l} className={`key lvl-${i}`}>{l}</span>)}
        {expected.length > 0 && <span className="key missed">Needed, not used</span>}
        {expected.length > 0 && <span className="key-check"><CheckIcon size={15} /> Needed and used</span>}
        <label className="seen-toggle">
          <input type="checkbox" checked={showSeen} onChange={(e) => setShowSeen(e.target.checked)} />
          Show search results
        </label>
      </div>
      <div className="flow">
        {nodes.length === 0 ? (
          <div className="empty"><TableIcon size={40} /><span>No tables yet</span></div>
        ) : (
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} proOptions={{ hideAttribution: true }}
                     colorMode={theme}
                     fitView fitViewOptions={{ padding: 0.15, maxZoom: 1.1 }}
                     nodesConnectable={false} onNodeClick={(_, n) => setPicked(n.id === picked ? null : n.id)}
                     onPaneClick={() => setPicked(null)}>
            <Background gap={20} color="var(--grid)" />
            <Controls showInteractive={false} />
          </ReactFlow>
        )}
      </div>
      {detail && (
        <div className="table-detail">
          <div className="detail-head">
            <b>{detail.name}</b>
            <span className="muted">
              {pickedUse ? `${LEVELS[pickedUse.level]} · step ${pickedUse.steps.join(", ")}` : "Not used by the agent"}
            </span>
          </div>
          <div className="columns">{detail.columns.join(" · ")}</div>
        </div>
      )}
    </div>
  );
}
