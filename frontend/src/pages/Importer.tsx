import React, { useState, useEffect, useRef } from "react";
import { api, post, Json, usePoll } from "../shared/api";
import { TrackingPanel } from "../components/TrackingPanel";
export function Importer({ onDone }: { onDone: (id: number) => void }) {
  const [path, P] = useState(""),
    [job, J] = useState<any>(null),
    [error, E] = useState("");
  useEffect(() => {
    if (
      !job ||
      ["completed", "failed", "cancelled", "interrupted"].includes(job.status)
    )
      return;
    let active = true;
    const t = setInterval(
      () =>
        api("/import-jobs/" + job.id)
          .then((j) => {
            if (!active) return;
            J(j);
            if (j.status === "completed") onDone(j.snapshot_id);
          })
          .catch((e) => E(String(e))),
      800,
    );
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [job?.id, job?.status]);
  return (
    <section>
      <h3>Import historical project / 导入历史项目</h3>
      <div className="controls">
        <input
          aria-label="Import project path"
          value={path}
          onChange={(e) => P(e.target.value)}
          placeholder="Local project directory"
        />
        <button
          disabled={
            !path ||
            (job &&
              ["queued", "running", "committing", "cancelling"].includes(
                job.status,
              ))
          }
          onClick={() =>
            post("/import-jobs", { path })
              .then(J)
              .catch((e) => E(String(e)))
          }
        >
          Scan & snapshot
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {job && (
        <>
          <p>
            {job.status} · {job.current_file} · {job.processed}/{job.total}
          </p>
          {["queued", "running"].includes(job.status) && (
            <button
              onClick={() =>
                post("/import-jobs/" + job.id + "/cancel", {})
                  .then(J)
                  .catch((e) => E(String(e)))
              }
            >
              Cancel
            </button>
          )}
        </>
      )}
    </section>
  );
}
