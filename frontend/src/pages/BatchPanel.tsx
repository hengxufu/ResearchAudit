import React, { useState, useEffect, useRef } from "react";
import { api, post, Json, usePoll } from "../shared/api";
import { TrackingPanel } from "../components/TrackingPanel";
export function BatchPanel({ snapshot, id }: { snapshot: any; id: number }) {
  const [value, S] = useState<any>(null),
    [error, E] = useState("");
  return (
    <section>
      <h3>Batch final-metric comparison</h3>
      <p>
        按 model_version / dataset
        整理共同指标。评价元数据缺失或冲突时不汇总为可比均值。
      </p>
      <button
        onClick={() =>
          post("/v2/analyses/batch", {
            refs: snapshot.runs.map((r: any) => ({
              snapshot_id: id,
              run_id: r.id,
            })),
            group_by: ["model_version", "dataset"],
          })
            .then(S)
            .catch((e) => E(String(e)))
        }
      >
        Analyze all runs in snapshot
      </button>
      {error && <p role="alert">{error}</p>}
      {value && <Json value={value} />}
    </section>
  );
}
