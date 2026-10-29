import { useEffect, useState } from "react";
import { api, post, Json } from "./shared";
export function RegistryPanel({
  snapshot,
  id,
}: {
  snapshot: any;
  id: number | null;
}) {
  const [projects, P] = useState<any[]>([]),
    [experiments, E] = useState<any[]>([]),
    [project, X] = useState(""),
    [label, L] = useState(""),
    [experiment, V] = useState(""),
    [run, R] = useState(""),
    [error, S] = useState(""),
    [history, H] = useState<any[]>([]);
  async function refresh() {
    try {
      P((await api("/tracking/health")).projects);
      E(await api("/v2/experiments"));
      if (id) H(await api("/v2/snapshots/" + id + "/associations"));
    } catch (e) {
      S(String(e));
    }
  }
  useEffect(() => {
    refresh();
  }, [id]);
  return (
    <section>
      <h3>Project → Experiment → Run</h3>
      <p>
        先在总览注册追踪目录，再创建研究实验。关联由用户确认；修改保留历史，不自动合并来源。
      </p>
      <div className="controls">
        <select value={project} onChange={(e) => X(e.target.value)}>
          <option value="">Registered project</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.root}
            </option>
          ))}
        </select>
        <input
          value={label}
          onChange={(e) => L(e.target.value)}
          placeholder="Experiment label"
        />
        <button
          disabled={!project || !label}
          onClick={() =>
            post("/v2/experiments", { project_id: project, label })
              .then(refresh)
              .catch((e) => S(String(e)))
          }
        >
          Create experiment
        </button>
      </div>
      {snapshot && id && (
        <div className="controls my-3">
          <select value={experiment} onChange={(e) => V(e.target.value)}>
            <option value="">Experiment</option>
            {experiments.map((e) => (
              <option key={e.id} value={e.id}>
                {e.label}
              </option>
            ))}
          </select>
          <select value={run} onChange={(e) => R(e.target.value)}>
            <option value="">Selected snapshot Run</option>
            {snapshot.runs.map((r: any) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <button
            disabled={!run || !experiment}
            onClick={() =>
              post("/v2/associations", {
                snapshot_id: id,
                run_id: run,
                experiment_id: experiment,
              })
                .then(refresh)
                .catch((e) => S(String(e)))
            }
          >
            Confirm association
          </button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      <details>
        <summary>Association revisions / 关联历史</summary>
        <Json value={history} />
      </details>
    </section>
  );
}
