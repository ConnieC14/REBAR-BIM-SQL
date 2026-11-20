import { useEffect, useRef, useState } from "react";
import type { Example, Turn } from "../types";
import Answer from "./Answer";
import { ArrowIcon, BulbIcon, ChatIcon, GroupIcon, ListIcon, SendIcon } from "./Icons";

interface Props {
  turns: Turn[];
  selected: number | null;
  onSelect: (id: number) => void;
  onShowSteps: (id: number) => void;
  examples: Example[];
  onAsk: (question: string, example?: Example) => void;
  running: boolean;
}

type Tab = "chat" | "examples";

// The example questions as cards, grouped
function ExampleCards({ examples, onPick, running }: {
  examples: Example[]; onPick: (e: Example) => void; running: boolean;
}) {
  const groups = [...new Set(examples.map((e) => e.group))];
  return (
    <>
      {groups.map((group) => (
        <div key={group} className="start-group">
          <div className="group-label"><GroupIcon group={group} size={16} /> {group}</div>
          {examples.filter((e) => e.group === group).map((e) => (
            <button key={e.question} className="start-card" disabled={running} onClick={() => onPick(e)}>
              <span>{e.question}</span>
              <ArrowIcon size={18} />
            </button>
          ))}
        </div>
      ))}
    </>
  );
}

export default function AskPanel({ turns, selected, onSelect, onShowSteps, examples, onAsk, running }: Props) {
  const [text, setText] = useState("");
  const [tab, setTab] = useState<Tab>("chat");
  const bottom = useRef<HTMLDivElement>(null);

  // Follow the newest turn while it streams, and when coming back to the chat
  useEffect(() => {
    if (tab === "chat") bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, tab]);

  const ask = (question: string, example?: Example) => {
    setTab("chat");
    onAsk(question, example);
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!text.trim() || running) return;
    ask(text.trim());
    setText("");
  };

  return (
    <section className="panel ask">
      <div className="panel-bar">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "chat"} className={tab === "chat" ? "active" : ""}
                  onClick={() => setTab("chat")}><ChatIcon size={17} /> Chat</button>
          <button role="tab" aria-selected={tab === "examples"} className={tab === "examples" ? "active" : ""}
                  onClick={() => setTab("examples")}><BulbIcon size={17} /> Examples</button>
        </div>
      </div>
      <div className="ask-scroll">
        {tab === "examples" ? (
          <ExampleCards examples={examples} onPick={(e) => ask(e.question, e)} running={running} />
        ) : (
          <>
            {turns.length === 0 && (
              <div className="start">
                <h2 className="ask-empty">Ask about the building model</h2>
                <ExampleCards examples={examples} onPick={(e) => ask(e.question, e)} running={running} />
              </div>
            )}
            {turns.map((turn) => (
              <article key={turn.id} className={`turn ${turn.id === selected ? "selected" : ""}`}
                       onClick={() => onSelect(turn.id)}>
                <div className="question">{turn.question}</div>
                <Answer lane={turn.lanes.agent} label={turn.compare ? "agent" : undefined} />
                {turn.compare && <Answer lane={turn.lanes.baseline} label="baseline" />}
                <button className="see-steps link" onClick={(e) => { e.stopPropagation(); onShowSteps(turn.id); }}>
                  <ListIcon size={16} /> See steps
                </button>
              </article>
            ))}
            <div ref={bottom} />
          </>
        )}
      </div>

      <form className="ask-form" onSubmit={submit}>
        <input value={text} onChange={(e) => setText(e.target.value)} disabled={running}
               placeholder="Type a question…" aria-label="Question" />
        <button type="submit" className="primary" disabled={running || !text.trim()} aria-label="Ask">
          <SendIcon size={20} />
        </button>
      </form>
    </section>
  );
}
