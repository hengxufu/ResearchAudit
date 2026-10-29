import { useEffect, useState } from "react";
export async function api(path: string, options?: RequestInit) {
  const response = await fetch("/api" + path, options);
  if (!response.ok) throw Error(await response.text());
  return response.json();
}
export const post = (path: string, body: any) =>
  api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export function Json({ value }: { value: any }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}
export function usePoll(path: string, ms = 3000) {
  const [value, S] = useState<any>(null),
    [error, E] = useState("");
  useEffect(() => {
    let active = true;
    const run = () =>
      api(path)
        .then((v) => {
          if (active) S(v);
        })
        .catch((e) => {
          if (active) E(String(e));
        });
    run();
    const id = setInterval(run, ms);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [path, ms]);
  return { value, error };
}
