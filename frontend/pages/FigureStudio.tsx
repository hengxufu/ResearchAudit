import React, { useState, useEffect, useRef } from "react";
import { api, post, Json, usePoll } from "./shared";
import { TrackingPanel } from "../TrackingPanel";
export function FigureStudio({ snapshot, id }: { snapshot: any; id: number }) {
  const [metric, M] = useState(""),
    [kind, K] = useState("curve"),
    [filter, F] = useState(""),
    [smooth, S] = useState(false),
    [error, E] = useState("");
  const host = useRef<HTMLDivElement>(null);
  const metrics: string[] = [
    ...new Set<string>(
      snapshot.runs.flatMap((r: any) => Object.keys(r.series)),
    ),
  ];
  const spec = {
    snapshot_id: id,
    metric,
    kind,
    filter,
    smoothing: smooth ? "trailing 5 (display only)" : "none",
  };
  useEffect(() => {
    let active = true;
    let plot: any;
    import("plotly.js-dist-min")
      .then((module) => {
        plot = module.default;
        if (!active || !host.current) return;
        const runs = snapshot.runs.filter(
          (r: any) => r.series[metric] && r.name.includes(filter),
        );
        const traces =
          kind === "heatmap"
            ? [
                {
                  type: "heatmap",
                  z: runs.map((r: any) => r.series[metric]),
                  y: runs.map((r: any) => r.name),
                },
              ]
            : runs.map((r: any) => {
                const raw = r.series[metric];
                const y =
                  smooth && kind === "curve"
                    ? raw.map((v: any, i: number) => {
                        const a = raw.slice(Math.max(0, i - 4), i + 1);
                        return a.some((v: any) => v === null)
                          ? null
                          : a.reduce((a: number, b: number) => a + b, 0) /
                              a.length;
                      })
                    : raw;
                return {
                  name: r.name,
                  y,
                  x: kind === "curve" ? r.series[metric + "/step"] : undefined,
                  type: kind === "curve" ? "scatter" : kind,
                  mode: "lines",
                  connectgaps: false,
                };
              });
        plot.react(
          host.current,
          traces,
          {
            margin: { t: 30 },
            title: metric,
            xaxis: { title: kind === "curve" ? "Observation / step" : "" },
            yaxis: { title: metric },
            legend: { orientation: "h" },
          },
          { responsive: true, displaylogo: false },
        );
      })
      .catch((e) => E(String(e)));
    return () => {
      active = false;
      if (plot && host.current) plot.purge(host.current);
    };
  }, [snapshot, metric, kind, filter, smooth]);
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(spec, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "researchaudit-plot.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section>
      <h3>Figure Studio / 科研图表</h3>
      <div className="controls">
        <select
          aria-label="Figure metric"
          value={metric}
          onChange={(e) => M(e.target.value)}
        >
          <option value="">Select metric</option>
          {metrics.map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
        <select value={kind} onChange={(e) => K(e.target.value)}>
          {["curve", "box", "violin", "heatmap"].map((k) => (
            <option key={k}>{k}</option>
          ))}
        </select>
        <input
          value={filter}
          onChange={(e) => F(e.target.value)}
          placeholder="Run name filter"
        />
        <label>
          <input
            type="checkbox"
            checked={smooth}
            onChange={(e) => S(e.target.checked)}
          />
          Display smoothing
        </label>
        <button onClick={download}>Export plot configuration</button>
      </div>
      {error && <p role="alert">{error}</p>}
      <div ref={host} style={{ height: 440, minWidth: 250 }} />
      <div className="controls">
        {["png", "svg", "pdf"].map((f) => (
          <a
            key={f}
            href={
              "/api/projects/" +
              id +
              "/figure?metric=" +
              encodeURIComponent(metric) +
              "&format=" +
              f
            }
          >
            Raw curve {f.toUpperCase()} ↓
          </a>
        ))}
      </div>
      <p>
        后端导出使用原始曲线；Box / Violin / Heatmap 当前为交互视图，浏览器
        Plotly 工具栏可导出 PNG。
      </p>
    </section>
  );
}
