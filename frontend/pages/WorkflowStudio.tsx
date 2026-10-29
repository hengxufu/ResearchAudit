import { useEffect, useState } from "react";
import { api, post, Json, usePoll } from "./shared";
type Node = {
  id: string;
  kind: string;
  config: any;
  depends_on: string[];
  retries: number;
  condition?: any;
};
const kinds = [
  "import",
  "command",
  "describe",
  "batch",
  "audit",
  "figure",
  "report",
  "balance",
  "asset_verify",
];
export function WorkflowStudio() {
  const [name, N] = useState(""),
    [nodes, S] = useState<Node[]>([]),
    [definitions, D] = useState<any[]>([]),
    [selected, I] = useState<any>(null),
    [confirmed, C] = useState(false),
    [error, E] = useState(""),
    [detail, V] = useState<any>(null),
    [configText, K] = useState<Record<string, string>>({}),
    [conditionText, H] = useState<Record<string, string>>({});
  const { value: runs } = usePoll("/v3/workflow-runs", 1500);
  const refresh = async () => D(await api("/v3/workflows"));
  useEffect(() => {
    refresh().catch((e) => E(String(e)));
  }, []);
  async function act(fn: () => Promise<any>) {
    try {
      E("");
      const r = await fn();
      V(r);
      await refresh();
      return r;
    } catch (e) {
      E(String(e));
    }
  }
  function update(i: number, patch: Partial<Node>) {
    S(nodes.map((n, j) => (j === i ? { ...n, ...patch } : n)));
  }
  function load(d: any) {
    I(d);
    N(d.name);
    S(d.nodes);
    H(
      Object.fromEntries(
        d.nodes.map((n: Node) => [
          n.id,
          n.condition ? JSON.stringify(n.condition) : "",
        ]),
      ),
    );
    K(
      Object.fromEntries(
        d.nodes.map((n: Node) => [n.id, JSON.stringify(n.config, null, 2)]),
      ),
    );
  }
  function add() {
    let number = nodes.length + 1;
    while (nodes.some((n) => n.id === "step" + number)) number++;
    const id = "step" + number;
    const n = {
      id,
      kind: "import",
      config: { path: "" },
      depends_on: nodes.length ? [nodes[nodes.length - 1].id] : [],
      retries: 0,
    };
    S([...nodes, n]);
    K({ ...configText, [id]: JSON.stringify(n.config, null, 2) });
  }
  function template() {
    const ns: Node[] = [
      {
        id: "import",
        kind: "import",
        config: { path: "" },
        depends_on: [],
        retries: 0,
      },
      {
        id: "audit",
        kind: "audit",
        config: { snapshot_id: { $ref: "import.snapshot_id" } },
        depends_on: ["import"],
        retries: 0,
      },
      {
        id: "figure",
        kind: "figure",
        config: {
          snapshot_id: { $ref: "import.snapshot_id" },
          metric: "",
          format: "svg",
        },
        depends_on: ["import"],
        retries: 0,
      },
      {
        id: "report",
        kind: "report",
        config: { snapshot_id: { $ref: "import.snapshot_id" } },
        depends_on: ["import", "audit", "figure"],
        retries: 0,
      },
    ];
    I(null);
    H({});
    N("Import → audit → figure → report");
    S(ns);
    K(
      Object.fromEntries(
        ns.map((n) => [n.id, JSON.stringify(n.config, null, 2)]),
      ),
    );
  }
  return (
    <section>
      <h3>Research Workflow Studio / 工作流编排</h3>
      <p>
        配置真实 DAG。节点配置通过 <code>{'{"$ref":"node.snapshot_id"}'}</code>{" "}
        引用直接依赖输出；节点失败后阻断下游。重试会重新执行该命令，请仅用于允许重复运行的程序。
      </p>
      <div className="controls">
        <select
          aria-label="Workflow definition"
          value={selected?.id || ""}
          onChange={(e) => {
            const d = definitions.find((x) => x.id === e.target.value);
            if (d) load(d);
          }}
        >
          <option value="">New workflow / 新工作流</option>
          {definitions.map((d) => (
            <option value={d.id} key={d.id}>
              {d.name} · v{d.revision}
            </option>
          ))}
        </select>
        <button onClick={template}>
          Import/report template / 导入报告模板
        </button>
        <button
          onClick={() => {
            I(null);
            N("");
            S([]);
            K({});
          }}
        >
          New / 新建
        </button>
      </div>
      <label>
        Name / 名称{" "}
        <input
          aria-label="Workflow name"
          value={name}
          onChange={(e) => N(e.target.value)}
        />
      </label>
      <div className="workflow-nodes">
        {nodes.map((n, i) => (
          <article className="workflow-node" key={n.id}>
            <strong>{n.id}</strong>
            <label>
              Type / 节点类型{" "}
              <select
                aria-label={"Node kind " + n.id}
                value={n.kind}
                onChange={(e) => update(i, { kind: e.target.value })}
              >
                {kinds.map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
            </label>
            <label>
              Dependencies / 依赖
              <select
                multiple
                aria-label={"Dependencies " + n.id}
                value={n.depends_on}
                onChange={(e) =>
                  update(i, {
                    depends_on: Array.from(
                      e.target.selectedOptions,
                      (x) => x.value,
                    ),
                  })
                }
              >
                {nodes
                  .filter((x) => x.id !== n.id)
                  .map((x) => (
                    <option key={x.id}>{x.id}</option>
                  ))}
              </select>
            </label>
            <p>← {n.depends_on.join(", ") || "ROOT"}</p>
            <label>
              Config JSON
              <textarea
                aria-label={"Node config " + n.id}
                value={configText[n.id] ?? JSON.stringify(n.config, null, 2)}
                onChange={(e) => K({ ...configText, [n.id]: e.target.value })}
              />
            </label>
            <label>
              Retries{" "}
              <input
                type="number"
                min="0"
                max="2"
                value={n.retries}
                onChange={(e) => update(i, { retries: Number(e.target.value) })}
              />
            </label>
            <label>
              Condition JSON (optional)
              <input
                value={
                  conditionText[n.id] ??
                  (n.condition ? JSON.stringify(n.condition) : "")
                }
                onChange={(e) =>
                  H({ ...conditionText, [n.id]: e.target.value })
                }
              />
            </label>
            <button
              onClick={() => {
                S(nodes.filter((_, j) => i !== j));
              }}
            >
              Remove / 删除节点
            </button>
          </article>
        ))}
      </div>
      <button onClick={add}>Add node / 添加节点</button>{" "}
      <button
        disabled={!name || !nodes.length}
        onClick={() =>
          act(async () => {
            const payload = {
              name,
              description: selected?.description || "",
              nodes: nodes.map((n) => ({
                ...n,
                config: JSON.parse(configText[n.id]),
                condition: conditionText[n.id]
                  ? JSON.parse(conditionText[n.id])
                  : null,
              })),
            };
            const d = selected
              ? await api(
                  "/v3/workflows/" +
                    selected.id +
                    "?revision=" +
                    selected.revision,
                  {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                  },
                )
              : await post("/v3/workflows", payload);
            load(d);
            return d;
          })
        }
      >
        Save workflow / 保存版本
      </button>
      {selected && (
        <p>
          Definition {selected.id} · v{selected.revision}{" "}
          <button
            onClick={() =>
              act(() => api("/v3/workflows/" + selected.id + "/history"))
            }
          >
            Revision history
          </button>
        </p>
      )}
      <label>
        <input
          type="checkbox"
          aria-label="Confirm workflow execution"
          checked={confirmed}
          onChange={(e) => C(e.target.checked)}
        />{" "}
        已检查节点与命令，授权执行整个流程 / Authorize this workflow
      </label>
      <button
        disabled={!selected || !confirmed}
        onClick={() =>
          act(() =>
            post("/v3/workflows/" + selected.id + "/start", {
              revision: selected.revision,
              confirmed,
            }),
          )
        }
      >
        Run workflow / 执行工作流
      </button>
      <table>
        <thead>
          <tr>
            <th>Run</th>
            <th>State</th>
            <th>Node timeline / 节点时间线</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {(runs || []).map((r: any) => (
            <tr key={r.id}>
              <td>
                {r.id.slice(0, 10)} · v{r.revision}
              </td>
              <td>{r.state}</td>
              <td>
                {Object.entries(r.nodes).map(([id, n]: [string, any]) => (
                  <span key={id} className="node-status">
                    {id}: {n.state} ({n.attempts}){" "}
                    {n.output?.path && (
                      <a
                        href={
                          "/api/v3/workflow-runs/" + r.id + "/artifacts/" + id
                        }
                      >
                        ↓
                      </a>
                    )}
                  </span>
                ))}
              </td>
              <td>
                <button onClick={() => V(r)}>Inspect</button>
                <button
                  disabled={r.state !== "Running"}
                  onClick={() =>
                    act(() => post("/v3/workflow-runs/" + r.id + "/cancel", {}))
                  }
                >
                  Cancel
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {error && <p role="alert">{error}</p>}
      {detail && (
        <Json
          value={
            detail.workflow_id
              ? (runs || []).find((r: any) => r.id === detail.id) || detail
              : detail
          }
        />
      )}
    </section>
  );
}
