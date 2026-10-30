import React, { useState, useEffect, useRef } from "react";
import { api, post, Json, usePoll } from "../shared/api";
import { TrackingPanel } from "../components/TrackingPanel";
export function Assets() {
  const [items, S] = useState<any[]>([]),
    [path, P] = useState(""),
    [label, L] = useState(""),
    [kind, K] = useState("dataset"),
    [versions, V] = useState<any[]>([]),
    [selected, X] = useState(""),
    [error, E] = useState(""),
    [result, R] = useState<any>(null),
    [busy, B] = useState(false);
  async function refresh() {
    try {
      S(await api("/v2/assets"));
    } catch (e) {
      E(String(e));
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  async function action(fn: () => Promise<any>) {
    B(true);
    E("");
    try {
      R(await fn());
      await refresh();
      if (selected) V(await api("/v2/assets/" + selected + "/versions"));
    } catch (e) {
      E(String(e));
    } finally {
      B(false);
    }
  }
  return (
    <>
      <section>
        <h3>Reference-only data assets / 引用式数据资产</h3>
        <div className="controls">
          <input
            aria-label="Asset label"
            placeholder="Label / 名称"
            value={label}
            onChange={(e) => L(e.target.value)}
          />
          <input
            aria-label="Asset path"
            placeholder="Existing local path / 本地路径"
            value={path}
            onChange={(e) => P(e.target.value)}
          />
          <select value={kind} onChange={(e) => K(e.target.value)}>
            {["dataset", "model", "checkpoint", "result"].map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
          <button
            disabled={busy || !label || !path}
            onClick={() =>
              action(() => post("/v2/assets", { path, label, kind }))
            }
          >
            Register / 注册
          </button>
        </div>
        <p>
          默认不复制文件。元数据索引不能证明内容一致；Full hash 为显式完整读取。
        </p>
        {error && <p role="alert">{error}</p>}
        <table>
          <thead>
            <tr>
              <th>Label</th>
              <th>Kind</th>
              <th>Path</th>
              <th>Versions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}>
                <td>{a.label}</td>
                <td>{a.kind}</td>
                <td>{a.root}</td>
                <td>
                  <button
                    onClick={async () => {
                      X(a.id);
                      try {
                        V(await api("/v2/assets/" + a.id + "/versions"));
                      } catch (e) {
                        E(String(e));
                      }
                    }}
                  >
                    Open
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {selected && (
        <section>
          <h3>Immutable versions / 不可变版本</h3>
          <div className="controls">
            <button
              disabled={busy}
              onClick={() =>
                action(() => post("/v2/assets/" + selected + "/versions", {}))
              }
            >
              Metadata index
            </button>
            <button
              disabled={busy}
              onClick={() =>
                action(() =>
                  post(
                    "/v2/assets/" + selected + "/versions?hash_content=true",
                    {},
                  ),
                )
              }
            >
              Full SHA256 snapshot
            </button>
          </div>
          {busy && <p role="status">Processing local asset…</p>}
          {versions.map((v) => (
            <details key={v.id}>
              <summary>
                {v.id.slice(0, 16)} ·{" "}
                {new Date(v.created * 1000).toLocaleString()} ·{" "}
                {v.manifest.length} files
              </summary>
              <button
                disabled={busy}
                onClick={() =>
                  action(() =>
                    post("/v2/asset-versions/" + v.id + "/verify", {}),
                  )
                }
              >
                Verify references
              </button>
              <Json value={v} />
            </details>
          ))}
        </section>
      )}
      {result && (
        <section>
          <h3>Operation result</h3>
          <Json value={result} />
        </section>
      )}
    </>
  );
}
