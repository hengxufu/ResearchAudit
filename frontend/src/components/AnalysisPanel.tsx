import { useState } from "react";
export function AnalysisPanel({ snapshot, id }: { snapshot: any; id: number }) {
  const [run, R] = useState(""),
    [metric, M] = useState(""),
    [result, S] = useState<any>(null),
    [error, E] = useState("");
  const selected = snapshot.runs.find((r: any) => r.id === run);
  async function analyze() {
    try {
      const r = await fetch("/api/analyses/describe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ snapshot_id: id, run_id: run, metric }),
      });
      if (!r.ok) throw Error(await r.text());
      S(await r.json());
      E("");
    } catch (e) {
      E(String(e));
    }
  }
  return (
    <section>
      <h3 className="font-bold">Scientific Analysis / 科研统计</h3>
      <p className="text-xs text-slate-500 my-2">
        单 Run 观测描述，不将 Epoch 作为独立重复样本。分析记录保留来源与方法。
      </p>
      <div className="flex gap-2">
        <select
          aria-label="Analysis run"
          value={run}
          onChange={(e) => {
            R(e.target.value);
            M("");
            S(null);
          }}
        >
          <option value="">Run / 实验</option>
          {snapshot.runs.map((r: any) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Analysis metric"
          value={metric}
          onChange={(e) => {
            M(e.target.value);
            S(null);
          }}
        >
          <option value="">Metric / 指标</option>
          {selected &&
            Object.keys(selected.metrics).map((m) => (
              <option key={m}>{m}</option>
            ))}
        </select>
        <button disabled={!run || !metric} onClick={analyze}>
          Compute / 计算
        </button>
        <a href={"/api/projects/" + id + "/package"}>Evidence ZIP ↓</a>
        <a href={"/api/projects/" + id + "/report-export?format=html"}>
          HTML ↓
        </a>
        <a href={"/api/projects/" + id + "/report-export?format=json"}>
          JSON ↓
        </a>
      </div>
      {error && <p role="alert">{error}</p>}
      {result && (
        <>
          <p className="text-xs my-3">Analysis ID: {result.id}</p>
          <table className="text-sm">
            <tbody>
              {Object.entries(result.result).map(([k, v]) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td>{String(v ?? "UNKNOWN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
