import { useEffect, useState } from "react";
import { api } from "./shared";
export function GlobalSearch({
  query,
  onOpen,
}: {
  query: string;
  onOpen: (id: number) => void;
}) {
  const [items, S] = useState<any[]>([]);
  useEffect(() => {
    let active = true;
    if (query.trim().length < 2) {
      S([]);
      return;
    }
    const timer = setTimeout(
      () =>
        api("/history?" + new URLSearchParams({ q: query, limit: "5" }))
          .then((value) => {
            if (active) S(value.items);
          })
          .catch(() => {
            if (active) S([]);
          }),
      250,
    );
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);
  if (!items.length) return null;
  return (
    <div className="search-results">
      <p>Top matching runs / 实验检索</p>
      {items.map((r) => (
        <button
          key={r.snapshot_id + r.run_id}
          onClick={() => onOpen(r.snapshot_id)}
        >
          <strong>
            #{r.snapshot_id} {r.annotation.title || r.name}
          </strong>
          <small>{r.root}</small>
        </button>
      ))}
    </div>
  );
}
