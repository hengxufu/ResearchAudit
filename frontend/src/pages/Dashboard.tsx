import React, { useState, useEffect, useRef } from "react";
import { api, post, Json, usePoll } from "../shared/api";
import { TrackingPanel } from "../components/TrackingPanel";
export function Dashboard() {
  const { value, error } = usePoll("/v2/overview");
  const resources = usePoll("/v2/resources");
  return (
    <>
      <section>
        <h2>Local research workspace</h2>
        <p>
          数据记录完整性、实验复现性与科学正确性分别验证。所有展示值来自本地
          API。
        </p>
        {error && <p role="alert">{error}</p>}
        {value && (
          <>
            <div className="summary">
              <div>
                <b>{value.snapshots}</b>
                <span>Snapshots / 实验快照</span>
              </div>
              <div>
                <b>{value.assets}</b>
                <span>Assets / 数据资产</span>
              </div>
              <div>
                <b>{value.execution_states.Running}</b>
                <span>Running / 执行中</span>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Execution state</th>
                  <th>Count (latest 500)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(value.execution_states).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{String(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
      <section>
        <h3>System resources / 系统资源</h3>
        {resources.error && <p role="alert">{resources.error}</p>}
        {resources.value && (
          <>
            <p>
              CPU cores: {resources.value.logical_cpus} · RSS covers owned
              process trees. OS hard limits:{" "}
              {String(resources.value.hard_limits)}
            </p>
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>RSS MiB</th>
                  <th>CPU seconds</th>
                </tr>
              </thead>
              <tbody>
                {resources.value.active.map((r: any) => (
                  <tr key={r.run_id}>
                    <td>{r.run_id}</td>
                    <td>{(r.rss_bytes / 1048576).toFixed(1)}</td>
                    <td>{r.cpu_seconds.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p>
              GPU: {resources.value.gpu.status} · {resources.value.gpu.reason}
            </p>
          </>
        )}
      </section>
      {resources.value?.gpu?.gpus?.length > 0 && (
        <section>
          <h3>GPU telemetry (device-wide)</h3>
          <table>
            <thead>
              <tr>
                <th>GPU</th>
                <th>Utilization %</th>
                <th>Used / Total MiB</th>
              </tr>
            </thead>
            <tbody>
              {resources.value.gpu.gpus.map((gpu: any) => (
                <tr key={gpu.index}>
                  <td>{gpu.name}</td>
                  <td>{gpu.utilization_percent ?? "UNKNOWN"}</td>
                  <td>
                    {gpu.memory_used_mib ?? "UNKNOWN"} /{" "}
                    {gpu.memory_total_mib ?? "UNKNOWN"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      <TrackingPanel />
    </>
  );
}
