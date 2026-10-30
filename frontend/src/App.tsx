import { GlobalSearch } from "./pages/GlobalSearch";
import {
  ProjectIntelligence,
  AdvancedResearch,
  MultipanelStudio,
} from "./pages/PlatformV4";
import { InferencePanel } from "./pages/InferencePanel";
import { RegistryPanel } from "./pages/RegistryPanel";
import { ReproductionPanel } from "./pages/ReproductionPanel";
import { WorkflowStudio } from "./pages/WorkflowStudio";
import { DataStudio } from "./pages/DataStudio";
import { ResearchIntelligence } from "./pages/ResearchIntelligence";
import { KnowledgePanel } from "./pages/KnowledgePanel";
import React, { useEffect, useState, useRef } from "react";
import { ExecutionPanel } from "./components/ExecutionPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { api, post, Json } from "./shared/api";
import { Dashboard } from "./pages/Dashboard";
import { Assets } from "./pages/Assets";
import { Importer } from "./pages/Importer";
import { FigureStudio } from "./pages/FigureStudio";
import { GraphPanel } from "./pages/GraphPanel";
import { AuditPanel } from "./pages/AuditPanel";
import { PluginPanel } from "./pages/PluginPanel";
import { BatchPanel } from "./pages/BatchPanel";
const pages = [
  ["dashboard", "项目总览", "Dashboard"],
  ["projects", "项目与数据资产", "Project Explorer"],
  ["executions", "实验执行中心", "Experiment Center"],
  ["runs", "实验记录", "Run Explorer"],
  ["analysis", "科研分析", "Analysis Studio"],
  ["figures", "科研绘图", "Figure Studio"],
  ["provenance", "证据图谱", "Provenance Explorer"],
  ["audit", "科研审计", "Audit Center"],
  ["reports", "报告与成果", "Report Center"],
];
export default function App() {
  const [page, P] = useState("dashboard"),
    [en, L] = useState(false),
    [theme, T] = useState(localStorage.getItem("ra-theme") || "light"),
    [snapshots, S] = useState<any[]>([]),
    [id, I] = useState<number | null>(null),
    [snapshot, D] = useState<any>(null),
    [query, Q] = useState(""),
    [error, E] = useState("");
  const name = pages.find((p) => p[0] === page)!;
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("ra-theme", theme);
  }, [theme]);
  async function refresh() {
    try {
      S(await api("/projects"));
    } catch (e) {
      E(String(e));
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  const contextRequest = useRef(0);
  async function open(n: number) {
    try {
      const request = ++contextRequest.current;
      const result = await api("/projects/" + n);
      if (request !== contextRequest.current) return;
      D(result);
      I(n);
      await refresh();
    } catch (e) {
      E(String(e));
    }
  }
  const needs = [
    "analysis",
    "figures",
    "provenance",
    "audit",
    "reports",
  ].includes(page);
  return (
    <div className="workbench">
      <aside className="navigation">
        <div className="brand">
          ◈ ResearchAudit <small>4.0 development</small>
        </div>
        <input
          aria-label="Global navigation search"
          placeholder={en ? "Search pages" : "搜索功能页面"}
          value={query}
          onChange={(e) => Q(e.target.value)}
        />
        <GlobalSearch
          query={query}
          onOpen={(n) => {
            open(n);
            P("analysis");
          }}
        />
        <nav>
          {pages
            .filter((p) =>
              p.join(" ").toLowerCase().includes(query.toLowerCase()),
            )
            .map((p) => (
              <button
                key={p[0]}
                className={page === p[0] ? "active" : ""}
                onClick={() => P(p[0])}
              >
                {en ? p[2] : p[1]}
              </button>
            ))}
        </nav>
        <p className="local-note">LOCAL FIRST · EVIDENCE BASED</p>
      </aside>
      <main className="workspace">
        <header className="toolbar">
          <div>
            <p className="eyebrow">RESEARCH WORKSPACE</p>
            <h1>{en ? name[2] : name[1]}</h1>
          </div>
          <div className="controls">
            <button onClick={() => L(!en)}>中文 / EN</button>
            <button onClick={() => T(theme === "light" ? "dark" : "light")}>
              {theme === "light" ? "Dark / 深色" : "Light / 浅色"}
            </button>
          </div>
        </header>
        <section className="context">
          <label>
            Snapshot / 实验上下文{" "}
            <select
              aria-label="Snapshot context"
              value={id ?? ""}
              onChange={(e) => e.target.value && open(Number(e.target.value))}
            >
              <option value="">Select imported snapshot</option>
              {snapshots.map((s) => (
                <option key={s.id} value={s.id}>
                  #{s.id} · {s.root}
                </option>
              ))}
            </select>
          </label>
          <button onClick={refresh}>Refresh</button>
        </section>
        {error && <p role="alert">{error}</p>}
        {page === "dashboard" && <Dashboard />}
        {page === "projects" && (
          <>
            <Importer onDone={open} />
            <ProjectIntelligence />
            <RegistryPanel snapshot={snapshot} id={id} />
            <Assets />
            <DataStudio />
            <PluginPanel />
          </>
        )}
        {page === "executions" && (
          <>
            <ExecutionPanel
              onSnapshot={(n) => {
                open(n);
                P("analysis");
              }}
            />
            <ReproductionPanel />
            <WorkflowStudio />
          </>
        )}
        {page === "runs" && (
          <HistoryPanel
            en={en}
            onOpen={(n) => {
              open(n);
              P("analysis");
            }}
          />
        )}
        {needs && !snapshot && (
          <section>
            <h3>Select a snapshot / 选择实验上下文</h3>
            <p>
              先导入历史实验或执行科研程序，再选择顶部快照。页面不会生成模拟实验结果。
            </p>
          </section>
        )}
        {snapshot && id !== null && (
          <>
            {page === "analysis" && (
              <>
                <AnalysisPanel key={id} snapshot={snapshot} id={id} />
                <AdvancedResearch key={"v4" + id} snapshot={snapshot} id={id} />
                <BatchPanel snapshot={snapshot} id={id} />
                <InferencePanel key={id} snapshot={snapshot} id={id} />
                <PluginPanel />
                <ResearchIntelligence
                  key={"intelligence" + id}
                  snapshot={snapshot}
                  id={id}
                />
              </>
            )}
            {page === "figures" && (
              <>
                <FigureStudio key={id} snapshot={snapshot} id={id} />
                <MultipanelStudio
                  key={"multi" + id}
                  snapshot={snapshot}
                  id={id}
                />
              </>
            )}
            {page === "provenance" && (
              <>
                <GraphPanel id={id} />
                <KnowledgePanel snapshotId={id} />
              </>
            )}
            {page === "audit" && <AuditPanel key={id} id={id} />}
            {page === "reports" && (
              <section>
                <h3>Source-backed reports / 可追溯报告</h3>
                <p>
                  报告来自快照与版本化分析；归档不自动复制数据集和模型权重。
                </p>
                <div className="controls">
                  {[
                    ["Markdown", "/report"],
                    ["HTML", "/report-export?format=html"],
                    ["JSON", "/report-export?format=json"],
                    ["Evidence ZIP", "/package"],
                  ].map(([label, path]) => (
                    <a key={label} href={"/api/projects/" + id + path}>
                      {label} ↓
                    </a>
                  ))}
                  <a href={"/api/v2/snapshots/" + id + "/report.pdf"}>
                    PDF report ↓
                  </a>
                </div>
                <details>
                  <summary>Snapshot evidence manifest</summary>
                  <Json value={snapshot.evidence} />
                </details>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
