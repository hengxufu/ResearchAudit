import React, { useState, useEffect, useRef } from "react";
import { api, post, Json, usePoll } from "../shared/api";
import { TrackingPanel } from "../components/TrackingPanel";
export function AuditPanel({ id }: { id: number }) {
  const [record, R] = useState<any>(null),
    [history, H] = useState<any[]>([]),
    [status, S] = useState(""),
    [error, E] = useState(""),
    [full, F] = useState(false);
  async function run() {
    try {
      const r = await post("/v2/snapshots/" + id + "/audits", {
        full_hash: full,
      });
      R(r);
      H(await api("/v2/snapshots/" + id + "/audits"));
    } catch (e) {
      E(String(e));
    }
  }
  useEffect(() => {
    api("/v2/snapshots/" + id + "/audits")
      .then((v) => {
        H(v);
        R(v[0] || null);
      })
      .catch((e) => E(String(e)));
  }, [id]);
  return (
    <section>
      <h3>Versioned audit / 版本化科研审计</h3>
      <div className="controls">
        <label>
          <input
            type="checkbox"
            checked={full}
            onChange={(e) => F(e.target.checked)}
          />
          Full source hash verification
        </label>
        <button onClick={run}>Run audit</button>
        <select value={status} onChange={(e) => S(e.target.value)}>
          <option value="">All states</option>
          {["PASS", "WARN", "FAIL", "UNKNOWN"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          aria-label="Audit history"
          onChange={(e) => R(history.find((r) => r.id === e.target.value))}
          value={record?.id || ""}
        >
          <option value="">History</option>
          {history.map((r) => (
            <option key={r.id} value={r.id}>
              {new Date(r.created * 1000).toLocaleString()}
            </option>
          ))}
        </select>
      </div>
      {error && <p role="alert">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>Rule / Version</th>
            <th>Layer</th>
            <th>State</th>
            <th>Reason / Evidence</th>
          </tr>
        </thead>
        <tbody>
          {record?.findings
            .filter((f: any) => !status || status === f.status)
            .map((f: any, i: number) => (
              <tr key={i}>
                <td>
                  {f.rule} · {f.rule_version}
                </td>
                <td>{f.layer}</td>
                <td>
                  <span className={"status " + f.status}>{f.status}</span>
                </td>
                <td>
                  {typeof f.reason === "string"
                    ? f.reason
                    : JSON.stringify(f.reason)}
                  <details>
                    <summary>Evidence</summary>
                    <Json value={f.evidence} />
                  </details>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </section>
  );
}
