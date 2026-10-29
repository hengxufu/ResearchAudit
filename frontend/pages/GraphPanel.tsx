import React, { useState, useEffect, useRef } from "react";
import { api, post, Json, usePoll } from "./shared";
import { TrackingPanel } from "../TrackingPanel";
export function GraphPanel({ id }: { id: number }) {
  const [data, S] = useState<any>(null),
    [selected, X] = useState<any>(null),
    [error, E] = useState("");
  useEffect(() => {
    api("/v3/snapshots/" + id + "/graph")
      .then(S)
      .catch((e) => E(String(e)));
  }, [id]);
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading evidence…</p>;
  const nodes = data.nodes.slice(0, 100);
  const position = new Map<string, { x: number; y: number }>();
  const columns: any = { file: 0, imported_run: 1, metric: 2 };
  const count = [0, 0, 0, 0];
  nodes.forEach((n: any) => {
    const col = columns[n.type] ?? 3;
    position.set(n.id, { x: 20 + col * 230, y: 35 + count[col]++ * 72 });
  });
  const height = Math.max(220, Math.max(...count) * 72 + 40);
  return (
    <section>
      <h3>Observed / declared provenance</h3>
      <p>{data.scope} · 显示前 100 个节点；点击查看原始证据。</p>
      <button
        onClick={() =>
          api("/v3/snapshots/" + id + "/graph")
            .then((v) => {
              S(v);
              X(null);
            })
            .catch((e) => E(String(e)))
        }
      >
        Refresh evidence graph / 刷新证据图
      </button>
      <div className="graph-scroll">
        <svg
          width="940"
          height={height}
          role="img"
          aria-label="Provenance graph"
        >
          {data.edges.map((e: any, i: number) => {
            const a = position.get(e.from),
              b = position.get(e.to);
            return a && b ? (
              <line
                key={i}
                x1={a.x + 185}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="#94a3b8"
              />
            ) : null;
          })}
          {nodes.map((n: any) => {
            const p = position.get(n.id)!;
            return (
              <g key={n.id} onClick={() => X(n)} style={{ cursor: "pointer" }}>
                <rect
                  x={p.x}
                  y={p.y - 20}
                  width="185"
                  height="45"
                  rx="6"
                  fill={n.type === "file" ? "#dbeafe" : "#ccfbf1"}
                />
                <text x={p.x + 8} y={p.y - 3} fontSize="11" fill="#0f172a">
                  {n.type}
                </text>
                <text x={p.x + 8} y={p.y + 14} fontSize="10" fill="#0f172a">
                  {String(
                    n.attributes?.name ||
                      n.attributes?.path ||
                      n.attributes?.label ||
                      n.id,
                  ).slice(0, 26)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      {selected && <Json value={selected} />}
    </section>
  );
}
