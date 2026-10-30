import { useState, useEffect } from "react";
import { api, post, Json } from "./shared";
export function ProjectIntelligence() {
  const [path, P] = useState(""),
    [documents, D] = useState<any[]>([]),
    [selected, S] = useState<any>(null),
    [result, R] = useState<any>(null),
    [error, E] = useState(""),
    [label, L] = useState(""),
    [reason, Q] = useState(""),
    [candidate, C] = useState(""),
    [env, K] = useState("pip");
  const refresh = () => api("/v4/projects").then(D);
  useEffect(() => {
    refresh().catch((e) => E(String(e)));
  }, []);
  async function act(fn: () => Promise<any>) {
    try {
      E("");
      R(await fn());
      await refresh();
    } catch (e) {
      E(String(e));
    }
  }
  return (
    <section>
      <h3>Project Intelligence / 项目自动接管</h3>
      <p>
        只读结构扫描，静态 AST 识别
        Python/PyTorch；大数据和权重只记录位置与元数据。目录关联保留待确认状态。补录和监听分别启用。
      </p>
      <label>
        Existing project / 本地项目
        <input
          aria-label="Project intelligence path"
          value={path}
          onChange={(e) => P(e.target.value)}
        />
      </label>
      <button
        disabled={!path}
        onClick={() =>
          act(async () => {
            const d = await post("/v4/projects/inspect", { path });
            S(d);
            return d;
          })
        }
      >
        Inspect project / 分析项目
      </button>
      <select
        aria-label="Discovered project"
        value={selected?.id || ""}
        onChange={(e) => S(documents.find((d) => d.id === e.target.value))}
      >
        <option value="">Select indexed project</option>
        {documents.map((d) => (
          <option key={d.id} value={d.id}>
            {d.root} · v{d.revision}
          </option>
        ))}
      </select>
      {selected && (
        <>
          <p>
            Structures: {selected.structures.join(", ")} ·{" "}
            {selected.files.length} indexed files ·{" "}
            {selected.truncated ? "TRUNCATED" : "bounded scan complete"}
          </p>
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Evidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {selected.candidates.map((c: any) => (
                <tr key={c.directory}>
                  <td>{c.directory}</td>
                  <td>{c.files.join(", ")}</td>
                  <td>{c.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            onClick={() =>
              act(() =>
                post("/v4/projects/" + selected.id + "/backfill", {
                  directories: selected.candidates.map((c: any) => c.directory),
                }),
              )
            }
          >
            Backfill candidates / 批量补录
          </button>
          <button
            onClick={() =>
              act(() => post("/v4/projects/" + selected.id + "/watch", {}))
            }
          >
            Enable continuous tracking / 开启持续追踪
          </button>
          <label>
            Candidate directory
            <input value={candidate} onChange={(e) => C(e.target.value)} />
          </label>
          <label>
            Experiment label
            <input value={label} onChange={(e) => L(e.target.value)} />
          </label>
          <label>
            Review reason
            <input value={reason} onChange={(e) => Q(e.target.value)} />
          </label>
          <button
            disabled={!label || !reason}
            onClick={() =>
              act(async () => {
                const d = await post(
                  "/v4/projects/" + selected.id + "/associations",
                  {
                    directory: candidate,
                    experiment_label: label,
                    reason,
                    revision: selected.revision,
                  },
                );
                S(d);
                return d;
              })
            }
          >
            Record reviewed association / 记录修正
          </button>
        </>
      )}
      <details>
        <summary>Environment declarations / 环境声明与差异</summary>
        <p>
          使用上方路径填写 requirements.txt 或 Conda
          YAML。解析不安装依赖，不执行文件。对比对象是本服务运行器，跨目标环境一致性仍单独标为
          UNKNOWN。
        </p>
        <select value={env} onChange={(e) => K(e.target.value)}>
          <option>pip</option>
          <option>conda</option>
        </select>
        <button
          disabled={!path}
          onClick={() =>
            act(async () => {
              const d = await post("/v4/environments/import", {
                path,
                kind: env,
              });
              return {
                declaration: d,
                comparison: await post(
                  "/v4/environments/" + d.id + "/compare",
                  {},
                ),
              };
            })
          }
        >
          Import and compare / 导入并核验
        </button>
      </details>
      {error && <p role="alert">{error}</p>}
      {result && <Json value={result} />}
    </section>
  );
}
export function AdvancedResearch({
  snapshot,
  id,
}: {
  snapshot: any;
  id: number;
}) {
  const [metric, M] = useState(
      Object.keys(snapshot.runs[0]?.metrics || {})[0] || "",
    ),
    [space, S] = useState('{"x":[0,1]}'),
    [algorithm, A] = useState("bayesian"),
    [proposal, P] = useState<any>(null),
    [result, R] = useState<any>(null),
    [error, E] = useState(""),
    [spec, X] = useState('{"argv":[],"cwd":""}'),
    [confirmed, C] = useState(false),
    [candidate, I] = useState(0),
    [group, G] = useState("model"),
    [paired, B] = useState(false),
    [independent, D] = useState(false),
    [text, T] = useState("哪些实验缺失随机种子"),
    [operation, O] = useState("query");
  const refs = snapshot.runs.map((r: any) => ({
    snapshot_id: id,
    run_id: r.id,
  }));
  async function act(fn: () => Promise<any>) {
    try {
      E("");
      R(await fn());
    } catch (e) {
      E(String(e));
    }
  }
  return (
    <section>
      <h3>Advanced Research & Optimization / 科研分析与优化</h3>
      <p>
        输入来自当前快照的真实 Run。Bootstrap 的样本单位为独立运行或匹配
        seed，算法建议与实际执行分开；优化需要控制评价协议与非搜索变量。
      </p>
      <label>
        Objective / metric
        <input
          aria-label="Optimization metric"
          value={metric}
          onChange={(e) => M(e.target.value)}
        />
      </label>
      <label>
        Parameter space / 有限参数区间 JSON
        <textarea
          aria-label="Optimization space"
          value={space}
          onChange={(e) => S(e.target.value)}
        />
      </label>
      <select
        aria-label="Optimization algorithm"
        value={algorithm}
        onChange={(e) => A(e.target.value)}
      >
        {["bayesian", "grid", "random"].map((a) => (
          <option key={a}>{a}</option>
        ))}
      </select>
      <button
        onClick={() =>
          act(async () => {
            const p = await post("/v4/optimizations", {
              refs,
              metric,
              space: JSON.parse(space),
              algorithm,
              count: 3,
              budget: 3,
              seed: 7,
            });
            P(p);
            return p;
          })
        }
      >
        Suggest experiments / 生成候选
      </button>
      {proposal && (
        <>
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Parameters</th>
                <th>Prediction / SD</th>
              </tr>
            </thead>
            <tbody>
              {proposal.candidates.map((c: any, i: number) => (
                <tr key={i}>
                  <td>{i}</td>
                  <td>{JSON.stringify(c.parameters)}</td>
                  <td>
                    {c.predicted_mean ?? "N/A"} / {c.posterior_sd ?? "N/A"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <label>
            Candidate index
            <input
              type="number"
              min="0"
              max={proposal.candidates.length - 1}
              value={candidate}
              onChange={(e) => I(Number(e.target.value))}
            />
          </label>
          <label>
            Explicit command Spec JSON (argv supports {"{parameter}"})
            <textarea
              aria-label="Optimization command"
              value={spec}
              onChange={(e) => X(e.target.value)}
            />
          </label>
          <label>
            <input
              aria-label="Authorize optimization execution"
              type="checkbox"
              checked={confirmed}
              onChange={(e) => C(e.target.checked)}
            />{" "}
            已审阅命令，授权本地执行该候选
          </label>
          <button
            disabled={!confirmed}
            onClick={() =>
              act(() =>
                post("/v4/optimizations/" + proposal.id + "/dispatch", {
                  candidate,
                  spec: JSON.parse(spec),
                  confirmed,
                }),
              )
            }
          >
            Execute candidate / 执行候选
          </button>
          <button
            onClick={() =>
              act(() => api("/v4/optimizations/" + proposal.id + "/results"))
            }
          >
            Refresh actual results / 更新真实结果
          </button>
        </>
      )}
      <details>
        <summary>Registered statistics / 分层与重复测量统计</summary>
        <label>
          Group/condition parameter
          <input value={group} onChange={(e) => G(e.target.value)} />
        </label>
        <label>
          <input
            type="checkbox"
            checked={paired}
            onChange={(e) => B(e.target.checked)}
          />{" "}
          两条件 seed 匹配 Bootstrap
        </label>
        <label>
          <input
            type="checkbox"
            checked={independent}
            onChange={(e) => D(e.target.checked)}
          />{" "}
          已确认独立运行 / 独立 seed block 假设
        </label>
        <button
          onClick={() =>
            act(() =>
              post("/v4/statistics/bootstrap", {
                refs,
                metric,
                group_by: [group],
                paired,
                independent,
                seed: 7,
                resamples: 2000,
              }),
            )
          }
        >
          Compute registered bootstrap / 计算
        </button>
      </details>
      <details>
        <summary>Local Research Copilot / 证据约束助手</summary>
        <p>
          本地白名单工具模式，无模型、无云端上传；不执行 SQL、Shell 或 Python。
        </p>
        <select value={operation} onChange={(e) => O(e.target.value)}>
          {["query", "summary", "audit", "analysis_plan"].map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
        <input
          aria-label="Copilot question"
          value={text}
          onChange={(e) => T(e.target.value)}
        />
        <button
          onClick={() =>
            act(() => post("/v4/copilot", { snapshot_id: id, operation, text }))
          }
        >
          Run evidence tool / 执行证据工具
        </button>
      </details>
      {error && <p role="alert">{error}</p>}
      {result && <Json value={result} />}
    </section>
  );
}
export function MultipanelStudio({
  snapshot,
  id,
}: {
  snapshot: any;
  id: number;
}) {
  const first = snapshot.runs[0];
  const metric = Object.keys(first?.metrics || {})[0] || "";
  const [configuration, C] = useState(
      JSON.stringify(
        {
          title: "Research figure",
          panels: [
            {
              label: metric,
              refs: first
                ? [{ snapshot_id: id, run_id: first.id, metric }]
                : [],
              smooth: 1,
              scale: "linear",
            },
          ],
        },
        null,
        2,
      ),
    ),
    [result, R] = useState<any>(null),
    [error, E] = useState("");
  return (
    <section>
      <h3>Reproducible multipanel / 可重建多子图</h3>
      <p>
        配置引用不可变快照；原始曲线始终保留。smooth 为尾随窗口均值，scale 可选
        linear/log，xlim 为显示区间。
      </p>
      <textarea
        aria-label="Multipanel configuration"
        style={{ width: "100%", minHeight: 180 }}
        value={configuration}
        onChange={(e) => C(e.target.value)}
      />
      <button
        onClick={async () => {
          try {
            E("");
            R(await post("/v4/figures", JSON.parse(configuration)));
          } catch (e) {
            E(String(e));
          }
        }}
      >
        Save figure recipe / 保存绘图配置
      </button>
      {result && (
        <>
          <p>Recipe {result.id}</p>
          {["svg", "pdf", "png"].map((f) => (
            <a
              style={{ marginRight: 15 }}
              key={f}
              href={"/api/v4/figures/" + result.id + "/" + f}
            >
              {f.toUpperCase()} ↓
            </a>
          ))}
          <Json value={result} />
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
