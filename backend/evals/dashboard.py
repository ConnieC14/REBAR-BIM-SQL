"""
Builds a self-contained HTML dashboard for one or more scored runs.

    python -m evals.dashboard evals/runs/<A> [evals/runs/<B> ...] [--out path.html]

Each run gets its own color (up to 4 runs). The file has no external
dependencies, so it can be opened locally or shared as-is.
"""
import os
import sys
import json
import argparse
import pandas as pd

from evals.common import RUNS_DIR

ROW_COLUMNS = ["id", "suite", "group", "tags", "repeat", "question", "answer", "final_sql",
               "behavior", "passed", "correct_result", "ex_strict", "ex_relaxed", "answer_match", "grounded",
               "field_accuracy", "steps", "sql_attempts", "sql_errors", "cost_usd", "latency_s"]
MAX_RUNS = 4


def load_run_data(run_dir: str) -> dict:
    with open(os.path.join(run_dir, "summary.json")) as summary_file:
        summary = json.load(summary_file)
    results = pd.read_csv(os.path.join(run_dir, "results.csv"))
    columns = [c for c in ROW_COLUMNS if c in results] + [c for c in results if c.startswith("chk_")]
    rows = json.loads(results[columns].to_json(orient="records"))

    details = {}
    with open(os.path.join(run_dir, "traces.jsonl")) as traces_file:
        for line in traces_file:
            trace = json.loads(line)
            sqls = [{"sql": e["sql"][:1500], "ok": e["ok"], "error": (e.get("error") or "")[:300],
                     "rows": e.get("row_count")}
                    for e in trace["events"] if e["kind"] == "sql"]
            details[f"{trace['item_id']}#{trace.get('repeat', 0)}"] = {
                "sql": sqls, "error": trace.get("error")}

    llm = summary.get("llm") or {}
    return {
        "name": os.path.basename(run_dir.rstrip("/")),
        "label": summary["run"],
        "llm": f"{llm.get('provider', '?')} / {llm.get('model', '?')}"
               + (f" / effort {llm['effort']}" if llm.get("effort") else ""),
        "summary": summary,
        "rows": rows,
        "details": details,
    }


def build_dashboard(run_dirs: list, out_path: str):
    runs = [load_run_data(run_dir) for run_dir in run_dirs[:MAX_RUNS]]
    data = json.dumps({"runs": runs}, default=str).replace("</", "<\\/")
    with open(out_path, "w") as out_file:
        out_file.write(TEMPLATE.replace("/*__DATA__*/null", data))
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--out", default=os.path.join(RUNS_DIR, "dashboard.html"))
    args = parser.parse_args()
    if len(args.runs) > MAX_RUNS:
        print(f"Showing the first {MAX_RUNS} runs only.")
    print(f"Wrote {build_dashboard(args.runs, args.out)}")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent Eval Dashboard</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --run-1: #2a78d6; --run-2: #eb6834; --run-3: #1baf7a; --run-4: #eda100;
  --good: #0ca30c; --good-text: #006300; --critical: #d03b3b; --warning: #fab219;
  --wash: rgba(42,120,214,0.08);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --run-1: #3987e5; --run-2: #d95926; --run-3: #199e70; --run-4: #c98500;
    --good-text: #0ca30c; --wash: rgba(57,135,229,0.12);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
  --run-1: #3987e5; --run-2: #d95926; --run-3: #199e70; --run-4: #c98500;
  --good-text: #0ca30c; --wash: rgba(57,135,229,0.12);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1180px; margin: 0 auto; padding: 24px 16px 48px; }
header { display: flex; flex-wrap: wrap; gap: 12px; align-items: baseline; justify-content: space-between; }
h1 { font-size: 22px; margin: 0; font-weight: 600; }
h2 { font-size: 15px; margin: 0 0 2px; font-weight: 600; }
.sub { color: var(--ink-2); font-size: 13px; margin: 0 0 12px; }
.runs { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }
.run-chip { display: flex; gap: 8px; align-items: center; padding: 6px 10px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; cursor: pointer; font-size: 13px; }
.run-chip input { margin: 0; }
.swatch { width: 10px; height: 10px; border-radius: 3px; flex: none; }
.run-chip .meta { color: var(--muted); }
button.theme { background: var(--surface); color: var(--ink); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px 10px; cursor: pointer; font: inherit; font-size: 13px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.tile { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }
.tile .label { color: var(--ink-2); font-size: 12px; }
.tile .value { font-size: 26px; font-weight: 600; margin-top: 2px; }
.tile .note { color: var(--muted); font-size: 12px; }
.delta { font-size: 12px; margin-top: 2px; }
.delta.good { color: var(--good-text); } .delta.bad { color: var(--critical); }
.delta.flat { color: var(--muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; min-width: 0; }
.legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--ink-2); margin: 4px 0 8px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
svg text { fill: var(--ink-2); font-size: 11px; font-variant-numeric: tabular-nums; }
svg .cat { fill: var(--ink); font-size: 12px; }
svg .val { fill: var(--ink-2); }
.tooltip { position: fixed; pointer-events: none; background: var(--surface); color: var(--ink);
  border: 1px solid var(--border); border-radius: 8px; padding: 6px 9px; font-size: 12px;
  box-shadow: 0 4px 14px rgba(0,0,0,0.12); display: none; z-index: 10; max-width: 280px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 10px; }
.filters select, .filters input { background: var(--page); color: var(--ink); border: 1px solid var(--border);
  border-radius: 6px; padding: 5px 8px; font: inherit; font-size: 13px; }
.filters input { flex: 1; min-width: 160px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; color: var(--ink-2); font-weight: 500; border-bottom: 1px solid var(--axis); padding: 6px 8px; white-space: nowrap; }
td { border-bottom: 1px solid var(--grid); padding: 6px 8px; vertical-align: top; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.id { white-space: nowrap; }
tr.item { cursor: pointer; }
tr.item:hover { background: var(--wash); }
.status { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.detail td { background: var(--page); }
.detail pre { white-space: pre-wrap; word-break: break-word; margin: 4px 0 10px; font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace;
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 8px; }
.detail .k { color: var(--ink-2); font-size: 12px; margin-top: 6px; }
.chk { display: inline-flex; gap: 4px; align-items: center; margin: 2px 8px 2px 0; font-size: 12px; }
.empty { color: var(--muted); padding: 16px 0; }
.count { color: var(--muted); font-size: 12px; }
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Agent eval dashboard</h1>
      <p class="sub">Text-to-SQL agent evaluation on WideWorldImporters: accuracy, safety and extraction suites.</p>
    </div>
    <button class="theme" id="theme" type="button">Toggle theme</button>
  </header>
  <div class="runs" id="runs"></div>
  <section class="tiles" id="tiles"></section>
  <section class="grid" id="charts"></section>
  <section class="card" style="margin-top:16px">
    <h2>Questions</h2>
    <p class="sub">One row per question run. Click a row for the answer, SQL attempts and checks.</p>
    <div class="filters">
      <select id="f-run"></select>
      <select id="f-suite"></select>
      <select id="f-result">
        <option value="all">All results</option><option value="pass">Passed</option><option value="fail">Failed</option>
      </select>
      <input id="f-search" type="search" placeholder="Search id, question or answer">
    </div>
    <div class="count" id="count"></div>
    <div class="table-wrap"><table id="table"></table></div>
  </section>
</main>
<div class="tooltip" id="tooltip"></div>
<script>
const DATA = /*__DATA__*/null;
const RUNS = DATA.runs.map((run, i) => ({ ...run, color: `var(--run-${i + 1})`, index: i }));
let selected = RUNS.map(r => r.name);
let openRow = null;

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const pct = v => v == null ? "–" : `${Math.round(v * 100)}%`;
const money = v => v == null ? "–" : (v < 0.01 && v > 0 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`);
const activeRuns = () => RUNS.filter(r => selected.includes(r.name));
// The text-to-SQL accuracy suite shown in tiles and charts (wwi_dev, bim_snowdon, ...)
const ACC = (() => {
  for (const run of RUNS) for (const [name, block] of Object.entries(run.summary.suites || {}))
    if (block.kind === "accuracy" || (!block.kind && name === "wwi_dev")) return name;
  return "wwi_dev";
})();
// The safety suite shown in tiles and charts (safety, safety_bim, ...)
const SAF = (() => {
  for (const run of RUNS) for (const [name, block] of Object.entries(run.summary.suites || {}))
    if (block.kind === "safety") return name;
  return "safety";
})();

// ---------- theme ----------
$("theme").onclick = () => {
  const root = document.documentElement;
  const dark = root.dataset.theme ? root.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
  try { localStorage.setItem("eval-theme", root.dataset.theme); } catch (e) {}
};
try { const saved = localStorage.getItem("eval-theme"); if (saved) document.documentElement.dataset.theme = saved; } catch (e) {}

// ---------- run selector ----------
function renderRunChips() {
  $("runs").innerHTML = RUNS.map(r => `
    <label class="run-chip">
      <input type="checkbox" data-run="${esc(r.name)}" ${selected.includes(r.name) ? "checked" : ""}>
      <span class="swatch" style="background:${r.color}"></span>
      <span><strong>${esc(r.label)}</strong> <span class="meta">${esc(r.llm)} · ${esc(r.name.slice(0, 19))}</span></span>
    </label>`).join("");
  $("runs").querySelectorAll("input").forEach(box => box.onchange = () => {
    selected = RUNS.filter(r => $("runs").querySelector(`[data-run="${CSS.escape(r.name)}"]`).checked).map(r => r.name);
    if (!selected.length) { selected = [box.dataset.run]; box.checked = true; }
    render();
  });
}

// ---------- stat tiles ----------
function metric(run, suite, key) {
  const block = run.summary.suites?.[suite];
  if (!block) return null;
  if (key in (block.metrics || {})) return block.metrics[key].mean;
  if (block[key] && typeof block[key] === "object") return block[key].mean;
  return null;
}
const TILES = [
  { label: "Retrieval complete", get: r => r.summary.suites?.[ACC]?.retrieval?.retrieval_complete?.mean ?? null, fmt: pct, up: true },
  { label: "Correct results", get: r => metric(r, ACC, "correct_result"), fmt: pct, up: true },
  { label: "Exact result (strict)", get: r => metric(r, ACC, "ex_strict"), fmt: pct, up: true },
  { label: "Answer matches gold", get: r => metric(r, ACC, "answer_match"), fmt: pct, up: true },
  { label: "Safety tests passed", get: r => metric(r, SAF, "safety_passed"), fmt: pct, up: true },
  { label: "Unsafe actions (attacks)", get: r => metric(r, SAF, "unsafe_action_rate"), fmt: pct, up: false },
  { label: "False refusals (benign)", get: r => metric(r, SAF, "false_refusal_rate"), fmt: pct, up: false },
  { label: "Extraction exact", get: r => metric(r, "extraction", "extract_exact"), fmt: pct, up: true },
  { label: "Total cost", get: r => r.summary.overall?.cost_usd, fmt: money, up: false,
    note: r => r.summary.overall ? `${money(r.summary.overall.cost_per_run_usd)} per question run` : "" },
  { label: "Mean latency", get: r => r.summary.overall?.latency_mean_s, fmt: v => v == null ? "–" : `${v.toFixed(1)}s`, up: false,
    note: r => r.summary.overall ? `p95 ${r.summary.overall.latency_p95_s}s` : "" },
];
function renderTiles() {
  const [primary, baseline] = activeRuns();
  $("tiles").innerHTML = TILES.map(t => {
    const value = t.get(primary);
    let delta = "";
    if (baseline) {
      const base = t.get(baseline);
      if (value != null && base != null) {
        const diff = value - base;
        const cls = Math.abs(diff) < 1e-9 ? "flat" : ((diff > 0) === t.up ? "good" : "bad");
        const arrow = cls === "flat" ? "→" : diff > 0 ? "▲" : "▼";
        const shown = t.fmt === pct ? `${diff > 0 ? "+" : ""}${Math.round(diff * 100)} pts`
          : `${diff > 0 ? "+" : ""}${t.fmt(Math.abs(diff)).replace("$", diff < 0 ? "-$" : "$")}`;
        delta = `<div class="delta ${cls}">${arrow} ${shown} vs ${esc(baseline.label)}</div>`;
      }
    }
    const note = t.note ? `<div class="note">${esc(t.note(primary))}</div>` : "";
    return `<div class="tile"><div class="label">${esc(t.label)}</div><div class="value">${t.fmt(value)}</div>${delta}${note}</div>`;
  }).join("");
}

// ---------- grouped horizontal bar chart ----------
function chartCard({ title, subtitle }, index) {
  const runs = activeRuns();
  const legend = runs.length > 1 ? `<div class="legend">${runs.map(r =>
    `<span><span class="swatch" style="background:${r.color}"></span>${esc(r.label)}</span>`).join("")}</div>` : "";
  return `<div class="card"><h2>${esc(title)}</h2><p class="sub">${esc(subtitle)}</p>${legend}<div class="chart" data-chart="${index}"></div></div>`;
}

// Draws at the container's real pixel width so text renders at its true size
function barSvg({ title, categories, value, info }, width) {
  const runs = activeRuns();
  const barH = runs.length > 1 ? 12 : 16, gap = 2, bandPad = 12;
  const labelW = Math.min(150, Math.round(width * 0.38)), valueW = 40;
  const plotW = width - labelW - valueW;
  const bandH = runs.length * barH + (runs.length - 1) * gap;
  const height = categories.length * (bandH + bandPad) + 22;
  const x = v => labelW + Math.max(0, Math.min(1, v)) * plotW;
  const showValues = runs.length <= 2;
  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(title)}">`;
  for (const tick of [0, 0.25, 0.5, 0.75, 1]) {
    svg += `<line x1="${x(tick)}" x2="${x(tick)}" y1="0" y2="${height - 18}" stroke="var(--${tick ? "grid" : "axis"})" stroke-width="1"/>`;
    svg += `<text x="${x(tick)}" y="${height - 4}" text-anchor="middle">${tick * 100}%</text>`;
  }
  categories.forEach((cat, ci) => {
    const top = ci * (bandH + bandPad) + 4;
    const maxChars = Math.floor((labelW - 10) / 6.5);
    svg += `<text class="cat" x="${labelW - 8}" y="${top + bandH / 2 + 4}" text-anchor="end">${esc(cat.length > maxChars ? cat.slice(0, maxChars - 1) + "…" : cat)}<title>${esc(cat)}</title></text>`;
    runs.forEach((run, ri) => {
      const v = value(run, cat);
      const y = top + ri * (barH + gap);
      if (v == null) {
        svg += `<text x="${labelW + 4}" y="${y + barH - 3}" class="val">no data</text>`;
        return;
      }
      const w = Math.max(x(v) - labelW, 0.5), r = Math.min(4, w, barH / 2);
      const path = `M${labelW},${y} h${w - r} a${r},${r} 0 0 1 ${r},${r} v${barH - 2 * r} a${r},${r} 0 0 1 -${r},${r} h-${w - r} z`;
      const tip = `${run.label} · ${cat}: ${pct(v)}${info ? " · " + info(run, cat) : ""}`;
      svg += `<path d="${path}" fill="${run.color}"/>`;
      svg += `<rect x="${labelW}" y="${y - gap / 2}" width="${plotW}" height="${barH + gap}" fill="transparent" data-tip="${esc(tip)}"/>`;
      if (showValues) svg += `<text class="val" x="${x(v) + 4}" y="${y + barH - 3}">${pct(v)}</text>`;
    });
  });
  svg += "</svg>";
  return svg;
}

const groupRate = (suite) => (run, cat) => run.summary.suites?.[suite]?.by_group?.[cat]?.passed?.mean ?? null;
const groupInfo = (suite) => (run, cat) => {
  const r = run.summary.suites?.[suite]?.by_group?.[cat]?.passed;
  return r && r.n ? `n=${r.n}, 95% CI ${pct(r.ci95[0])}–${pct(r.ci95[1])}` : "";
};
const groupsOf = (suite, order) => {
  const found = new Set();
  RUNS.forEach(r => Object.keys(r.summary.suites?.[suite]?.by_group || {}).forEach(g => found.add(g)));
  return order ? order.filter(g => found.has(g)).concat([...found].filter(g => !order.includes(g))) : [...found].sort();
};
const FAILURES = { dialect_error: "Wrong SQL dialect", schema_error: "Invented table/column", step_limit: "Hit step limit",
  ungrounded: "Ungrounded number", timeout: "Query timeout", crash: "Pipeline crash" };

let chartSpecs = [];
function drawCharts() {
  document.querySelectorAll("[data-chart]").forEach(el => {
    el.innerHTML = barSvg(chartSpecs[+el.dataset.chart], Math.max(260, el.clientWidth));
  });
}
let resizeTimer;
addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawCharts, 120); });

function renderCharts() {
  const charts = [];
  const barChart = spec => charts.push(spec);
  const difficulties = groupsOf(ACC, ["easy", "medium", "hard"]);
  if (difficulties.length) barChart(({ title: "Accuracy by difficulty",
    subtitle: `${ACC} · correct results (the answer's query returns the gold rows; extra columns and duplicates allowed)`,
    categories: difficulties, value: groupRate(ACC), info: groupInfo(ACC) }));
  if (RUNS.some(r => r.summary.suites?.[ACC]?.retrieval)) {
    barChart(({ title: "Retrieval complete by difficulty",
      subtitle: `${ACC} · every table the gold query needs appeared in retrieved context`,
      categories: difficulties,
      value: (run, cat) => run.summary.suites?.[ACC]?.retrieval?.by_group?.[cat]?.mean ?? null,
      info: (run, cat) => { const r = run.summary.suites?.[ACC]?.retrieval?.by_group?.[cat];
        return r && r.n ? `n=${r.n}, 95% CI ${pct(r.ci95[0])}–${pct(r.ci95[1])}` : ""; } }));
    const CELLS = { found_and_correct: "Found tables, correct", found_but_wrong: "Found tables, wrong",
      missed_but_correct: "Missed tables, correct", missed_and_wrong: "Missed tables, wrong" };
    barChart(({ title: "Where answers go wrong",
      subtitle: `${ACC} · share of runs by retrieval outcome and answer correctness`,
      categories: Object.values(CELLS),
      value: (run, cat) => {
        const key = Object.keys(CELLS).find(k => CELLS[k] === cat);
        return run.summary.suites?.[ACC]?.retrieval?.attribution?.[key] ?? null;
      } }));
  }
  const categories = groupsOf(SAF);
  if (categories.length) barChart(({ title: "Safety tests passed by category",
    subtitle: "safety · expected behavior and every check passed; benign_control measures over-refusal",
    categories, value: groupRate(SAF), info: groupInfo(SAF) }));
  const extraction = groupsOf("extraction", ["easy", "medium", "hard"]);
  if (extraction.length) barChart(({ title: "Extraction exact match by difficulty",
    subtitle: "extraction · every requested JSON field correct",
    categories: extraction, value: groupRate("extraction"), info: groupInfo("extraction") }));
  if (RUNS.some(r => r.summary.suites?.[ACC])) barChart(({ title: "Failure mix",
    subtitle: `${ACC} · share of question runs showing each failure (lower is better)`,
    categories: Object.values(FAILURES),
    value: (run, cat) => {
      const key = Object.keys(FAILURES).find(k => FAILURES[k] === cat);
      return run.summary.suites?.[ACC]?.failure_mix?.[key] ?? null;
    } }));
  chartSpecs = charts;
  $("charts").innerHTML = charts.map(chartCard).join("") || `<div class="empty">No scored suites yet.</div>`;
  drawCharts();
}

// ---------- tooltip ----------
document.addEventListener("mousemove", e => {
  const tip = e.target.closest?.("[data-tip]");
  const box = $("tooltip");
  if (!tip) { box.style.display = "none"; return; }
  box.textContent = tip.dataset.tip;
  box.style.display = "block";
  const left = Math.min(e.clientX + 14, innerWidth - box.offsetWidth - 8);
  box.style.left = `${left}px`;
  box.style.top = `${e.clientY + 14}px`;
});

// ---------- table ----------
function setupFilters() {
  $("f-run").innerHTML = `<option value="all">All selected runs</option>` +
    RUNS.map(r => `<option value="${esc(r.name)}">${esc(r.label)}</option>`).join("");
  const suites = [...new Set(RUNS.flatMap(r => r.rows.map(row => row.suite)))];
  $("f-suite").innerHTML = `<option value="all">All suites</option>` + suites.map(s => `<option>${esc(s)}</option>`).join("");
  ["f-run", "f-suite", "f-result"].forEach(id => $(id).onchange = renderTable);
  $("f-search").oninput = renderTable;
}

function statusCell(passed) {
  if (passed == null) return `<span class="status"><span class="dot" style="background:var(--muted)"></span>n/a</span>`;
  return passed ? `<span class="status"><span class="dot" style="background:var(--good)"></span>✓ Pass</span>`
    : `<span class="status"><span class="dot" style="background:var(--critical)"></span>✗ Fail</span>`;
}

function detailHtml(run, row) {
  const detail = run.details[`${row.id}#${row.repeat ?? 0}`] || { sql: [] };
  const checks = Object.keys(row).filter(k => k.startsWith("chk_") && row[k] != null)
    .map(k => `<span class="chk">${row[k] ? "✓" : "✗"} ${esc(k.slice(4).replace(/_/g, " "))}</span>`).join("");
  const sqls = detail.sql.map((s, i) => `<div class="k">Attempt ${i + 1} · ${s.ok ? `ok, ${s.rows ?? 0} rows` : "error"}</div>
    <pre>${esc(s.sql)}${s.ok ? "" : "\n\n" + esc(s.error)}</pre>`).join("") || `<div class="k">No SQL was executed.</div>`;
  return `<div class="k">Question</div><pre>${esc(row.question)}</pre>
    <div class="k">Answer · behavior: ${esc(row.behavior)}</div><pre>${esc(row.answer ?? "(none)")}</pre>
    ${detail.error ? `<div class="k">Pipeline error</div><pre>${esc(detail.error)}</pre>` : ""}
    ${checks ? `<div class="k">Safety checks</div><div>${checks}</div>` : ""}
    <div class="k">SQL attempts</div>${sqls}`;
}

function renderTable() {
  const runFilter = $("f-run").value, suite = $("f-suite").value, result = $("f-result").value;
  const query = $("f-search").value.trim().toLowerCase();
  const rows = [];
  activeRuns().filter(r => runFilter === "all" || r.name === runFilter).forEach(run => run.rows.forEach(row => {
    if (suite !== "all" && row.suite !== suite) return;
    if (result === "pass" && row.passed !== 1) return;
    if (result === "fail" && row.passed === 1) return;
    if (query && !`${row.id} ${row.question} ${row.answer}`.toLowerCase().includes(query)) return;
    rows.push({ run, row });
  }));
  $("count").textContent = `${rows.length} question runs`;
  const multi = activeRuns().length > 1;
  let html = `<thead><tr>${multi ? "<th>Run</th>" : ""}<th>ID</th><th>Group</th><th>Result</th><th>Behavior</th>
    <th class="num">SQL (errors)</th><th class="num">Cost</th><th class="num">Time</th><th>Question</th></tr></thead><tbody>`;
  rows.slice(0, 600).forEach(({ run, row }, i) => {
    const key = `${run.name}|${row.id}|${row.repeat}`;
    html += `<tr class="item" data-key="${esc(key)}">
      ${multi ? `<td><span class="status"><span class="swatch" style="background:${run.color}"></span>${esc(run.label)}</span></td>` : ""}
      <td class="id">${esc(row.id)}${row.repeat ? ` <span class="count">r${row.repeat}</span>` : ""}</td><td>${esc(row.group)}</td>
      <td>${statusCell(row.passed)}</td><td>${esc(row.behavior)}</td>
      <td class="num">${row.sql_attempts} (${row.sql_errors})</td><td class="num">${money(row.cost_usd)}</td>
      <td class="num">${row.latency_s == null ? "–" : row.latency_s.toFixed(1) + "s"}</td><td>${esc(row.question)}</td></tr>`;
    if (openRow === key) html += `<tr class="detail"><td colspan="${multi ? 9 : 8}">${detailHtml(run, row)}</td></tr>`;
  });
  html += "</tbody>";
  $("table").innerHTML = rows.length ? html : `<tr><td class="empty">No question runs match these filters.</td></tr>`;
  $("table").querySelectorAll("tr.item").forEach(tr => tr.onclick = () => {
    openRow = openRow === tr.dataset.key ? null : tr.dataset.key;
    renderTable();
  });
}

function render() { renderRunChips(); renderTiles(); renderCharts(); renderTable(); }
setupFilters();
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
