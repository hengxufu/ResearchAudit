import { useEffect, useState } from "react";
import { api, post, Json, usePoll } from "../shared/api";
export function ReproductionPanel() {
  const { value: runs } = usePoll("/executions");
  const [records, R] = useState<any[]>([]),
    [source, S] = useState(""),
    [tolerance, T] = useState('{"loss":{"atol":0.000001,"rtol":0.0001}}'),
    [inputs, I] = useState(""),
    [confirmed, C] = useState(false),
    [result, V] = useState<any>(null),
    [error, E] = useState("");
  const refresh = async () => R(await api("/v3/reproductions"));
  useEffect(() => {
    refresh().catch((e) => E(String(e)));
  }, []);
  async function act(action: () => Promise<any>) {
    try {
      E("");
      V(await action());
      await refresh();
    } catch (e) {
      E(String(e));
    }
  }
  return (
    <section>
      <h3>Experiment reproduction / 实验复现</h3>
      <p>
        显式重新运行历史执行；环境、数据、执行和数值一致性分别评定。清单只保存已声明的代码范围，外部依赖不视为已锁定。
      </p>
      <label>
        Source execution / 历史运行{" "}
        <select
          aria-label="Reproduction source"
          value={source}
          onChange={(e) => S(e.target.value)}
        >
          <option value="">Select successful execution</option>
          {(runs || [])
            .filter((r: any) => r.state === "Succeeded")
            .map((r: any) => (
              <option key={r.id} value={r.id}>
                {r.id.slice(0, 12)} · {r.spec.argv.join(" ")}
              </option>
            ))}
        </select>
      </label>
      <label>
        Metric tolerances / 指标容差 JSON{" "}
        <textarea
          aria-label="Reproduction tolerances"
          value={tolerance}
          onChange={(e) => T(e.target.value)}
        />
      </label>
      <label>
        Input asset version IDs / 输入版本（逗号分隔）
        <input value={inputs} onChange={(e) => I(e.target.value)} />
      </label>
      <button
        disabled={!source}
        onClick={() =>
          act(() =>
            post("/v3/reproductions", {
              source_execution: source,
              input_versions: inputs
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
              tolerances: JSON.parse(tolerance),
            }),
          )
        }
      >
        Create manifest / 创建复现清单
      </button>
      <label>
        <input
          type="checkbox"
          aria-label="Confirm reproduction execution"
          checked={confirmed}
          onChange={(e) => C(e.target.checked)}
        />{" "}
        我已检查历史命令，授权在本机重新执行 / Authorize local replay
      </label>
      <table>
        <thead>
          <tr>
            <th>Manifest</th>
            <th>Revision / State</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id}>
              <td>{r.id.slice(0, 12)}</td>
              <td>
                {r.revision} · {r.status}
              </td>
              <td>
                <a href={"/api/v3/reproductions/" + r.id + "/manifest.json"}>
                  Manifest JSON ↓
                </a>{" "}
                <button
                  disabled={
                    !confirmed || (r.execution && r.status !== "Prepared")
                  }
                  onClick={() =>
                    act(() =>
                      post("/v3/reproductions/" + r.id + "/start", {
                        confirmed,
                      }),
                    )
                  }
                >
                  Replay / 复现执行
                </button>{" "}
                <button
                  onClick={() =>
                    act(() =>
                      post("/v3/reproductions/" + r.id + "/evaluate", {}),
                    )
                  }
                >
                  Evaluate / 复现验证
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {error && <p role="alert">{error}</p>}
      {result?.scorecard && (
        <div className="scorecard">
          {Object.entries(result.scorecard).map(([k, v]: [string, any]) => (
            <div key={k}>
              <strong>{k}</strong>
              <p className={v.status}>{v.status}</p>
              <small>{v.reason || v.method || v.scope}</small>
            </div>
          ))}
        </div>
      )}
      {result?.scorecard && (
        <a href={"/api/v3/reproduction-reports/" + result.id + ".json"}>
          Reproduction report JSON ↓
        </a>
      )}
      {result && <Json value={result} />}
    </section>
  );
}
