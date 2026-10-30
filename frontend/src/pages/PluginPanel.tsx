import React, { useState, useEffect, useRef } from "react";
import { api, post, Json, usePoll } from "../shared/api";
import { TrackingPanel } from "../components/TrackingPanel";
export function PluginPanel() {
  const [kind, K] = useState("simulation"),
    [path, P] = useState(""),
    [value, V] = useState<any>(null),
    [error, E] = useState(""),
    [definitions, D] = useState("{}");
  return (
    <section>
      <h3>Domain parsers / 专业领域解析</h3>
      <div className="controls">
        <select value={kind} onChange={(e) => K(e.target.value)}>
          {["deep_learning", "pose", "simulation"].map((k) => (
            <option key={k}>{k}</option>
          ))}
        </select>
        <input
          value={path}
          onChange={(e) => P(e.target.value)}
          placeholder="CSV / NPZ / HDF5 / TensorBoard file"
        />
        <button
          disabled={!path}
          onClick={() =>
            Promise.resolve()
              .then(() =>
                post("/v2/plugins/" + kind + "/parse", {
                  path,
                  definitions: JSON.parse(definitions),
                }),
              )
              .then(V)
              .catch((e) => E(String(e)))
          }
        >
          Parse local data
        </button>
      </div>
      <label>
        Metric units and evaluation definitions (JSON)
        <textarea
          className="w-full"
          aria-label="Plugin metric definitions"
          value={definitions}
          onChange={(e) => D(e.target.value)}
        />
      </label>
      {error && <p role="alert">{error}</p>}
      {value && <Json value={value} />}
    </section>
  );
}
