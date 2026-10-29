import { useEffect, useState } from "react";
async function api(path: string, options?: RequestInit) {
  const r = await fetch("/api" + path, options);
  if (!r.ok) throw Error(await r.text());
  return r.json();
}
export function ExecutionPanel({
  onSnapshot,
}: {
  onSnapshot: (id: number) => void;
}) {
  const [cwd, C] = useState(""),
    [argv, A] = useState('["python", "train.py"]'),
    [runs, R] = useState<any[]>([]),
    [error, E] = useState(""),
    [logs, L] = useState(""),
    [selected, S] = useState("");
  async function refresh() {
    try {
      R(await api("/executions"));
      if (selected) {
        const stdout = await api("/executions/" + selected + "/logs");
        const stderr = await api(
          "/executions/" + selected + "/logs?stream=stderr",
        );
        L(stdout.text + "\nSTDERR\n" + stderr.text);
      }
    } catch (e) {
      E(String(e));
    }
  }
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 1500);
    return () => clearInterval(id);
  }, [selected]);
  async function create() {
    try {
      await api("/executions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cwd, argv: JSON.parse(argv) }),
      });
      E("");
      await refresh();
    } catch (e) {
      E(String(e));
    }
  }
  async function action(id: string, action: string) {
    try {
      await api("/executions/" + id + "/" + action, { method: "POST" });
      await refresh();
    } catch (e) {
      E(String(e));
    }
  }
  return (
    <section>
      <h3 className="font-bold">Experiment Orchestrator / 实验执行中心</h3>
      <p className="text-xs text-slate-500 my-2">
        创建仅保存配置；点击启动才执行命令。输出目录通过
        RESEARCHAUDIT_OUTPUT_DIR 提供。暂停不受支持。
      </p>
      <div className="flex gap-2 flex-wrap">
        <input
          aria-label="Execution working directory"
          value={cwd}
          onChange={(e) => C(e.target.value)}
          placeholder="Working directory / 工作目录"
        />
        <input
          className="flex-1"
          aria-label="Execution argument array"
          value={argv}
          onChange={(e) => A(e.target.value)}
        />
        <button onClick={create}>Create Pending / 创建</button>
      </div>
      {error && (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      )}
      <div className="max-h-72 overflow-auto">
        <table className="text-xs w-full">
          <thead>
            <tr>
              <th>Command</th>
              <th>State</th>
              <th>Exit</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td>
                  {r.spec.argv.join(" ")}
                  <br />
                  {r.id}
                </td>
                <td>
                  {r.state}
                  <br />
                  {r.error}
                </td>
                <td>{r.exit_code ?? "—"}</td>
                <td>
                  {r.state === "Pending" && (
                    <button onClick={() => action(r.id, "start")}>
                      Start / 启动
                    </button>
                  )}
                  {["Queued", "Running", "Pending"].includes(r.state) && (
                    <button onClick={() => action(r.id, "cancel")}>
                      Cancel / 终止
                    </button>
                  )}
                  <button onClick={() => S(r.id)}>Logs</button>
                  <button onClick={() => action(r.id, "rerun")}>
                    Rerun draft
                  </button>
                  {r.snapshot_id && (
                    <button onClick={() => onSnapshot(r.snapshot_id)}>
                      Results
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected && (
        <pre className="bg-slate-900 text-slate-100 p-3 text-xs overflow-auto max-h-64 whitespace-pre-wrap">
          {logs}
        </pre>
      )}
    </section>
  );
}
