import { useState } from "react";
import { api, post, Json } from "../shared/api";
export function ResearchIntelligence({
  snapshot,
  id,
}: {
  snapshot: any;
  id: number;
}) {
  const [selectedRuns, SelectRuns] = useState<string[]>(
    snapshot.runs.map((r: any) => r.id),
  );
  const [question, Q] = useState("哪些实验没有记录随机种子和评价协议"),
    [metric, M] = useState("loss"),
    [run, U] = useState(snapshot.runs[0]?.id || ""),
    [window, W] = useState(5),
    [threshold, T] = useState(0.1),
    [result, R] = useState<any>(null),
    [error, E] = useState(""),
    [equation, J] = useState(
      '{"energy_metric":"energy","power_metric":"power","time_metric":"time","unit_energy":"J","unit_power":"W","unit_time":"s","atol":0.000001,"rtol":0.0001}',
    ),
    [pose, P] = useState(
      '{"columns":{"truth_quaternion":["qx","qy","qz","qw"],"prediction_quaternion":["px","py","pz","pw"],"truth_translation":["tx","ty","tz"],"prediction_translation":["ux","uy","uz"]},"quaternion_order":"xyzw","convention":"active","frame":"","translation_unit":"m"}',
    ),
    [x, X] = useState("h"),
    [y, Y] = useState("error"),
    [sample, F] = useState("");
  async function act(fn: () => Promise<any>) {
    try {
      E("");
      R(await fn());
    } catch (e) {
      E(String(e));
    }
  }
  const metrics = Array.from(
    new Set<string>(snapshot.runs.flatMap((r: any) => Object.keys(r.metrics))),
  );
  return (
    <section>
      <h3>Research Intelligence & Suites / 实验诊断与专业计算</h3>
      <p>
        本地确定性规则可回溯至输入数据。诊断为待研究人员核实的线索，不推断因果关系。自然语言查询支持“缺失信息”或“最好
        + 精确指标名”，排序前验证评价口径。
      </p>
      <label>
        Local question / 本地查询
        <input
          aria-label="Research question"
          value={question}
          onChange={(e) => Q(e.target.value)}
        />
      </label>
      <button
        onClick={() =>
          act(() =>
            post("/v3/intelligence/query", { snapshot_id: id, text: question }),
          )
        }
      >
        Query experiments / 查询实验
      </button>
      <label>
        Summary runs / 总结实验
        <select
          multiple
          aria-label="Summary runs"
          value={selectedRuns}
          onChange={(e) =>
            SelectRuns(Array.from(e.target.selectedOptions, (x) => x.value))
          }
        >
          {snapshot.runs.map((r: any) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </label>
      <button
        disabled={!selectedRuns.length}
        onClick={() =>
          act(() =>
            post("/v3/intelligence/summary", {
              snapshot_id: id,
              run_ids: selectedRuns,
            }),
          )
        }
      >
        Summarize selected runs / 总结所选实验
      </button>
      <div className="controls">
        <label>
          Run
          <select
            aria-label="Suite run"
            value={run}
            onChange={(e) => U(e.target.value)}
          >
            {snapshot.runs.map((r: any) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Loss / metric
          <select value={metric} onChange={(e) => M(e.target.value)}>
            <option value="loss">loss</option>
            {metrics
              .filter((m) => m !== "loss")
              .map((m) => (
                <option key={m}>{m}</option>
              ))}
          </select>
        </label>
        <label>
          Window
          <input
            type="number"
            min="2"
            value={window}
            onChange={(e) => W(Number(e.target.value))}
          />
        </label>
        <label>
          Relative threshold
          <input
            type="number"
            step="0.01"
            min="0.001"
            value={threshold}
            onChange={(e) => T(Number(e.target.value))}
          />
        </label>
        <button
          onClick={() =>
            act(() =>
              post("/v3/intelligence/diagnose", {
                snapshot_id: id,
                loss_metric: metric,
                window,
                relative_threshold: threshold,
              }),
            )
          }
        >
          Diagnose training / 训练诊断
        </button>
        <button
          onClick={() =>
            act(() => post("/v3/suites/training", { snapshot_id: id, metric }))
          }
        >
          Training history / 最佳观测与检查点
        </button>
      </div>
      <details>
        <summary>Simulation equations / 仿真方程与数值分析</summary>
        <p>
          E(t) − E(0) − ∫P_net dt =
          0，梯形积分。必须包含全部净功率，当前实现需先转换为 J/W/s。
        </p>
        <textarea
          aria-label="Energy balance configuration"
          value={equation}
          onChange={(e) => J(e.target.value)}
        />
        <button
          onClick={() =>
            act(() =>
              post("/v3/suites/energy-balance", {
                snapshot_id: id,
                run_id: run,
                ...JSON.parse(equation),
              }),
            )
          }
        >
          Verify energy balance / 能量平衡
        </button>
        <div className="controls">
          <label>
            x column
            <input value={x} onChange={(e) => X(e.target.value)} />
          </label>
          <label>
            y column
            <input value={y} onChange={(e) => Y(e.target.value)} />
          </label>
          {["convergence", "sensitivity"].map((kind) => (
            <button
              key={kind}
              onClick={() =>
                act(() =>
                  post("/v3/suites/simulation-trend", {
                    snapshot_id: id,
                    run_id: run,
                    x_metric: x,
                    y_metric: y,
                    kind,
                  }),
                )
              }
            >
              {kind === "convergence"
                ? "Grid/time convergence / 收敛分析"
                : "Sensitivity / 单参数敏感性"}
            </button>
          ))}
        </div>
      </details>
      <details>
        <summary>Pose & failure samples / 位姿与失败样本</summary>
        <p>
          四元数归一化后计算 SO(3)
          测地角；真值和预测必须已对齐到相同坐标系及旋转约定。不会自动猜测评价协议。
        </p>
        <textarea
          aria-label="Pose evaluation configuration"
          value={pose}
          onChange={(e) => P(e.target.value)}
        />
        <button
          onClick={() =>
            act(() =>
              post("/v3/suites/pose", {
                snapshot_id: id,
                run_id: run,
                ...JSON.parse(pose),
              }),
            )
          }
        >
          Evaluate pose / 评价位姿
        </button>
        <label>
          Classification sample file / 样本表相对路径
          <input
            value={sample}
            onChange={(e) => F(e.target.value)}
            placeholder="sample_id,target,prediction CSV"
          />
        </label>
        <button
          disabled={!sample}
          onClick={() =>
            act(() =>
              api(
                "/projects/" +
                  id +
                  "/samples?path=" +
                  encodeURIComponent(sample),
              ),
            )
          }
        >
          Failure samples / 失败样本与类别分布
        </button>
      </details>
      {error && <p role="alert">{error}</p>}
      {result?.id && <p>Persisted analysis / 分析记录: {result.id}</p>}
      {result && <Json value={result} />}
    </section>
  );
}
