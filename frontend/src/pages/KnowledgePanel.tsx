import { useEffect, useState } from "react";
import { api, post, Json } from "../shared/api";
export function KnowledgePanel({ snapshotId }: { snapshotId: number }) {
  const [records, R] = useState<any[]>([]),
    [selected, I] = useState<any>(null),
    [kind, K] = useState("claim"),
    [title, T] = useState(""),
    [body, B] = useState(""),
    [conditions, C] = useState(""),
    [support, S] = useState("[]"),
    [conflict, F] = useState("[]"),
    [query, Q] = useState(""),
    [result, V] = useState<any>(null),
    [error, E] = useState("");
  const refresh = async (q = "") =>
    R(await api("/v3/knowledge?q=" + encodeURIComponent(q)));
  useEffect(() => {
    refresh().catch((e) => E(String(e)));
  }, [snapshotId]);
  async function act(fn: () => Promise<any>) {
    try {
      E("");
      V(await fn());
      await refresh(query);
    } catch (e) {
      E(String(e));
    }
  }
  function load(r: any) {
    I(r);
    K(r.kind);
    T(r.title);
    B(r.body);
    C(r.conditions);
    S(JSON.stringify(r.supporting, null, 2));
    F(JSON.stringify(r.conflicting, null, 2));
  }
  return (
    <section>
      <h3>Research Knowledge / 科研知识与 Claim–Evidence</h3>
      <p>
        笔记、假设、实验设计和结论保留修订历史；支持证据与冲突证据并列记录。存在证据链接不表示结论已经验证。
      </p>
      <div className="controls">
        <input
          aria-label="Knowledge search"
          value={query}
          onChange={(e) => Q(e.target.value)}
          placeholder="全文检索 / Full-text search"
        />
        <button
          onClick={() =>
            act(() => api("/v3/knowledge?q=" + encodeURIComponent(query)))
          }
        >
          Search / 搜索
        </button>
        <button
          onClick={() => {
            I(null);
            T("");
            B("");
            C("");
            S("[]");
            F("[]");
          }}
        >
          New record / 新记录
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Type / State</th>
            <th>Revision</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id}>
              <td>{r.title}</td>
              <td>
                {r.kind} · {r.validation_status}
              </td>
              <td>{r.revision}</td>
              <td>
                <button onClick={() => load(r)}>Edit / 修订</button>
                <button
                  onClick={() =>
                    act(() => api("/v3/knowledge/" + r.id + "/history"))
                  }
                >
                  History
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <label>
        Record type
        <select value={kind} onChange={(e) => K(e.target.value)}>
          {["note", "hypothesis", "design", "claim", "issue", "milestone"].map(
            (k) => (
              <option key={k}>{k}</option>
            ),
          )}
        </select>
      </label>
      <label>
        Title
        <input
          aria-label="Knowledge title"
          value={title}
          onChange={(e) => T(e.target.value)}
        />
      </label>
      <label>
        Content / 内容
        <textarea
          aria-label="Knowledge body"
          value={body}
          onChange={(e) => B(e.target.value)}
        />
      </label>
      <label>
        Applicable conditions / 适用条件
        <textarea value={conditions} onChange={(e) => C(e.target.value)} />
      </label>
      <button
        onClick={() => {
          try {
            S(
              JSON.stringify(
                [
                  ...JSON.parse(support),
                  { kind: "snapshot", id: String(snapshotId) },
                ],
                null,
                2,
              ),
            );
            E("");
          } catch (e) {
            E(String(e));
          }
        }}
      >
        Link current snapshot / 关联当前快照
      </button>
      <label>
        Supporting evidence JSON
        <textarea
          aria-label="Supporting evidence"
          value={support}
          onChange={(e) => S(e.target.value)}
        />
      </label>
      <label>
        Conflicting evidence JSON
        <textarea value={conflict} onChange={(e) => F(e.target.value)} />
      </label>
      <button
        disabled={!title}
        onClick={() =>
          act(async () => {
            const payload = {
              kind,
              title,
              body,
              conditions,
              supporting: JSON.parse(support),
              conflicting: JSON.parse(conflict),
              validation_status: "unverified",
            };
            const r = selected
              ? await api(
                  "/v3/knowledge/" +
                    selected.id +
                    "?revision=" +
                    selected.revision,
                  {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                  },
                )
              : await post("/v3/knowledge", payload);
            load(r);
            return r;
          })
        }
      >
        Save knowledge revision / 保存知识版本
      </button>
      {error && <p role="alert">{error}</p>}
      {result && <Json value={result} />}
    </section>
  );
}
