import type { Model } from "../types";
import { ChipIcon, CloudIcon, ColumnsIcon, LockIcon, MoonIcon, SunIcon } from "./Icons";

interface Props {
  models: Model[];
  model: string;
  onModel: (id: string) => void;
  compare: boolean;
  onCompare: (on: boolean) => void;
  theme: "light" | "dark";
  onTheme: () => void;
  disabled: boolean;
}

// Up to this many models show as buttons, more as a dropdown
const MAX_BUTTONS = 3;

export default function Header({ models, model, onModel, compare, onCompare, theme, onTheme, disabled }: Props) {
  const current = models.find((m) => m.id === model);
  return (
    <header className="header">
      <div className="brand">
        <span className="brand-name">REBAR</span>
        <span className="brand-sub">Snowdon Towers</span>
      </div>
      <div className="header-controls">
        {models.length > MAX_BUTTONS ? (
          <label className="model-select">
            {current?.local ? <ChipIcon size={16} /> : <CloudIcon size={16} />}
            <select value={model} disabled={disabled} onChange={(e) => onModel(e.target.value)}
                    aria-label="Model">
              {models.map((m) => (
                <option key={m.id} value={m.id}>{m.label}{m.note ? ` (${m.note})` : ""}</option>
              ))}
            </select>
          </label>
        ) : (
          <div className="segmented" role="radiogroup" aria-label="Model">
            {models.map((m) => (
              <button key={m.id} role="radio" aria-checked={m.id === model} disabled={disabled}
                      className={m.id === model ? "active" : ""} onClick={() => onModel(m.id)}
                      title={`${m.label} (${m.note})`}>
                {m.local ? <ChipIcon size={16} /> : <CloudIcon size={16} />}
                <span className="long">{m.label}</span>
                <span className="short">{m.short}</span>
                <span className="seg-note">{m.note}</span>
              </button>
            ))}
          </div>
        )}
        <label className="switch" title="Run the baseline pipeline next to the agent">
          <input type="checkbox" checked={compare} disabled={disabled}
                 onChange={(e) => onCompare(e.target.checked)} />
          <span className="switch-track" />
          <ColumnsIcon size={16} />
          <span className="switch-label">Compare</span>
        </label>
        <span className="pill" title="Writes are blocked before they reach the database">
          <LockIcon size={15} /> <span className="pill-label">Read-only</span>
        </span>
        <button className="icon-button" onClick={onTheme}
                aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
    </header>
  );
}
