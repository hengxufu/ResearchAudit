import { useState } from "react";
import { api, post, Json } from "../shared/api";
export function InferencePanel({
  snapshot,
  id,
}: {
  snapshot: any;
  id: number;
}) {
  const [metric, M] = useState(""),
    [mode, T] = useState("independent"),
    [groups, G] = useState<Record<string, string>>({}),
    [assume, A] = useState(false),
    [normal, N] = useState(false),
    [result, S] = useState<any>(null),
    [error, E] = useState(""),
    [family, F] = useState<string[]>([]);
  const metrics = [
    ...new Set<string>(
      snapshot.runs.flatMap((r: any) => Object.keys(r.metrics)),
    ),
  ];
  async function run() {
    try {
      const refs = (group: string) =>
        snapshot.runs
          .filter((r: any) => groups[r.id] === group)
          .sort((a: any, b: any) =>
            String(a.params.seed).localeCompare(String(b.params.seed)),
          )
          .map((r: any) => ({ snapshot_id: id, run_id: r.id, metric }));
      const body =
        mode === "paired"
          ? {
              left: refs("a"),
              right: refs("b"),
              independent_pairs: assume,
              normal_differences: normal,
            }
          : { left: refs("a"), right: refs("b"), independent_runs: assume };
      const value = await post(
        mode === "paired" ? "/analyses/paired" : "/v2/analyses/independent",
        body,
      );
      S(value);
      F([...family, value.id]);
      E("");
    } catch (e) {
      E(String(e));
    }
  }
  return (
    <section>
      <h3>Run-level statistical design / 实验级统计设计</h3>
      <p>
        至少每组 3 个独立 Run。配对模式按记录的 seed 对齐；Epoch
        不作为样本。假设由研究人员确认，程序不会自动证明独立性。
      </p>
      <div className="controls">
        <select
          aria-label="Inference metric"
          value={metric}
          onChange={(e) => M(e.target.value)}
        >
          <option value="">Metric</option>
          {metrics.map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
        <select value={mode} onChange={(e) => T(e.target.value)}>
          <option value="independent">Independent / Welch</option>
          <option value="paired">Paired seed / t-test</option>
        </select>
        <label>
          <input
            type="checkbox"
            checked={assume}
            onChange={(e) => A(e.target.checked)}
          />
          Independent runs/pairs declared
        </label>
        {mode === "paired" && (
          <label>
            <input
              type="checkbox"
              checked={normal}
              onChange={(e) => N(e.target.checked)}
            />
            Approximately normal paired differences declared
          </label>
        )}
      </div>
      <div className="max-h-64 overflow-auto">
        <table>
          <thead>
            <tr>
              <th>Run</th>
              <th>Seed</th>
              <th>Final metric</th>
              <th>Group</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.runs.map((r: any) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td>{r.params.seed ?? "UNKNOWN"}</td>
                <td>{r.metrics[metric] ?? "—"}</td>
                <td>
                  <select
                    aria-label={"Group " + r.name}
                    value={groups[r.id] || ""}
                    onChange={(e) => G({ ...groups, [r.id]: e.target.value })}
                  >
                    <option value="">Exclude</option>
                    <option value="a">A</option>
                    <option value="b">B</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="controls">
        <button disabled={!metric || !assume} onClick={run}>
          Compute planned comparison
        </button>
        <button
          disabled={!family.length}
          onClick={() =>
            post("/v2/analyses/holm", { ids: [...new Set(family)] })
              .then(S)
              .catch((e) => E(String(e)))
          }
        >
          Holm correction for this session family ({family.length})
        </button>
        <button onClick={() => F([])}>Clear test family</button>
      </div>
      {error && <p role="alert">{error}</p>}
      {result && <Json value={result} />}
    </section>
  );
}
