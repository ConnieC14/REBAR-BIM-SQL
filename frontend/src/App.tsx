import { useEffect, useState } from "react";
import Header from "./components/Header";
import AskPanel from "./components/AskPanel";
import WorkPanel from "./components/WorkPanel";
import { AgentIcon, ChatIcon } from "./components/Icons";
import { getExamples, getModels, getSchema, streamQuery } from "./api";
import { applyEvent, emptyLane } from "./state";
import type { Example, Model, Schema, Turn } from "./types";
import "./App.css";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem("rebar-theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // storage blocked: fall back to the system setting
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function App() {
  const [models, setModels] = useState<Model[]>([]);
  const [model, setModel] = useState("qwen");
  const [compare, setCompare] = useState(false);
  const [schema, setSchema] = useState<Schema | null>(null);
  const [examples, setExamples] = useState<Example[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [offline, setOffline] = useState(false);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [view, setView] = useState<"chat" | "work">("chat");   // narrow windows show one panel

  useEffect(() => {
    getModels().then((m) => { setModels(m.models); setModel(m.default_model); }).catch(() => setOffline(true));
    getSchema().then(setSchema).catch(() => setOffline(true));
    getExamples().then(setExamples).catch(() => setOffline(true));
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("rebar-theme", theme);
    } catch {
      // not saved; the theme still applies for this visit
    }
  }, [theme]);

  const ask = async (question: string, example?: Example) => {
    const id = Date.now();
    const turn: Turn = {
      id, question, model, compare, expected: example?.tables ?? [],
      lanes: compare ? { agent: emptyLane(), baseline: emptyLane() } : { agent: emptyLane() },
    };
    setTurns((t) => [...t, turn]);
    setSelected(id);
    setRunning(true);
    const update = (fn: (t: Turn) => Turn) => setTurns((all) => all.map((t) => (t.id === id ? fn(t) : t)));
    try {
      await streamQuery({ question, model, compare, profile: example?.profile ?? "default" }, (event) => {
        if (event.type === "busy") throw new Error("The agent is busy with another question.");
        update((t) => applyEvent(t, event));
      });
    } catch (e) {
      const error = e instanceof Error ? e.message : String(e);
      update((t) => ({
        ...t,
        lanes: Object.fromEntries(Object.entries(t.lanes).map(([k, l]) =>
          [k, l.done ? l : { ...l, done: true, stop: "error", error }])),
      }));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="app">
      <Header models={models} model={model} onModel={setModel} compare={compare} onCompare={setCompare}
              theme={theme} onTheme={() => setTheme(theme === "dark" ? "light" : "dark")} disabled={running} />
      {offline && <div className="banner">Can't reach the backend on port 8000.</div>}
      <nav className="view-switch segmented" aria-label="Panel">
        <button className={view === "chat" ? "active" : ""} onClick={() => setView("chat")}>
          <ChatIcon size={17} /> Chat
        </button>
        <button className={view === "work" ? "active" : ""} onClick={() => setView("work")}>
          <AgentIcon size={17} /> Agent
          {running && <span className="live-dot" aria-label="working" />}
        </button>
      </nav>
      <main className={`main view-${view}`}>
        <AskPanel turns={turns} selected={selected} onSelect={setSelected} examples={examples}
                  onShowSteps={(id) => { setSelected(id); setView("work"); }}
                  onAsk={ask} running={running} />
        <WorkPanel turn={turns.find((t) => t.id === selected)} schema={schema} theme={theme} />
      </main>
    </div>
  );
}

export default App;
