import { useEffect, useState } from "react";
import { api, post, Json } from "../shared/api";
export function DataStudio() {
  const [assets, A] = useState<any[]>([]),
    [asset, I] = useState(""),
    [path, P] = useState(""),
    [files, F] = useState<any[]>([]),
    [info, V] = useState<any>(null),
    [result, R] = useState<any>(null),
    [key, K] = useState(""),
    [slices, S] = useState("[[0,1,1]]"),
    [offset, O] = useState(0),
    [error, E] = useState("");
  async function act(fn: () => Promise<any>) {
    try {
      E("");
      R(await fn());
    } catch (e) {
      E(String(e));
    }
  }
  async function listing(id: string, p = "") {
    try {
      F(await api("/v3/assets/" + id + "/files?path=" + encodeURIComponent(p)));
    } catch (e) {
      E(String(e));
    }
  }
  useEffect(() => {
    api("/v2/assets")
      .then(A)
      .catch((e) => E(String(e)));
  }, []);
  return (
    <section>
      <h3>Research Data Studio / 科研数据浏览</h3>
      <p>
        先在数据资产中注册目录或文件。HDF5 按切片读取，NPY 使用内存映射，NPZ
        单成员解压限制 64
        MiB；不反序列化模型权重。预览为当前文件，版本完整性需单独校验。
      </p>
      <button
        onClick={() =>
          api("/v2/assets")
            .then(A)
            .catch((e) => E(String(e)))
        }
      >
        Refresh assets
      </button>
      <select
        aria-label="Data Studio asset"
        value={asset}
        onChange={(e) => {
          I(e.target.value);
          P("");
          V(null);
          R(null);
          listing(e.target.value);
        }}
      >
        <option value="">Select asset / 选择资产</option>
        {assets.map((a) => (
          <option value={a.id} key={a.id}>
            {a.label} · {a.kind}
          </option>
        ))}
      </select>
      <div className="controls">
        {files.map((f) => (
          <button
            key={f.path}
            onClick={() => {
              if (f.directory) listing(asset, f.path);
              else {
                P(f.path);
                O(0);
                V(null);
                R(null);
              }
            }}
          >
            {f.directory ? "▸" : "▤"} {f.path}
          </button>
        ))}
        {asset && <button onClick={() => listing(asset)}>Root / 根目录</button>}
      </div>
      <label>
        Relative file / 相对路径
        <input
          aria-label="Data Studio file"
          value={path}
          onChange={(e) => P(e.target.value)}
        />
      </label>
      <button
        disabled={!asset}
        onClick={() =>
          act(async () => {
            const r = await api(
              "/v3/assets/" +
                asset +
                "/inspect?path=" +
                encodeURIComponent(path),
            );
            V(r);
            if (r.fields?.length) {
              K(r.fields[0].key);
              S(
                JSON.stringify(
                  r.fields[0].shape.map((n: number) => [0, Math.min(n, 8), 1]),
                ),
              );
            }
            return r;
          })
        }
      >
        Inspect structure / 检查结构
      </button>
      {info?.fields?.length > 0 && (
        <div>
          <select
            aria-label="Array field"
            value={key}
            onChange={(e) => K(e.target.value)}
          >
            {info.fields.map((f: any) => (
              <option value={f.key} key={f.key}>
                {f.key} {JSON.stringify(f.shape)} · {f.dtype}
              </option>
            ))}
          </select>
          <label>
            Slice [start, stop, step] per dimension
            <input
              aria-label="Array slices"
              value={slices}
              onChange={(e) => S(e.target.value)}
            />
          </label>
          <button
            onClick={() =>
              act(() =>
                post("/v3/assets/" + asset + "/slice", {
                  path,
                  key,
                  slices: JSON.parse(slices),
                }),
              )
            }
          >
            Read slice / 读取切片
          </button>
        </div>
      )}
      {info?.image && (
        <img
          alt="Local scientific image preview"
          style={{ maxWidth: "100%", maxHeight: 400 }}
          src={
            "/api/v3/assets/" +
            asset +
            "/image?path=" +
            encodeURIComponent(path)
          }
        />
      )}
      {asset && (
        <div className="controls">
          <input
            aria-label="Table offset"
            type="number"
            min="0"
            value={offset}
            onChange={(e) => O(Number(e.target.value))}
          />
          <button
            onClick={() =>
              act(() =>
                api(
                  "/v3/assets/" +
                    asset +
                    "/table?path=" +
                    encodeURIComponent(path) +
                    "&offset=" +
                    offset +
                    "&limit=50",
                ),
              )
            }
          >
            Read table page / 分页读取
          </button>
          <button
            disabled={offset === 0}
            onClick={() => O(Math.max(0, offset - 50))}
          >
            −50
          </button>
          <button onClick={() => O(offset + 50)}>+50</button>
        </div>
      )}
      {asset && path.endsWith(".ipynb") && (
        <button
          onClick={() =>
            act(() =>
              post(
                "/v3/assets/" +
                  asset +
                  "/notebook?path=" +
                  encodeURIComponent(path),
                {},
              ),
            )
          }
        >
          Import stored notebook outputs / 导入 Notebook 已存结果
        </button>
      )}
      {error && <p role="alert">{error}</p>}
      {result?.rows && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {Object.keys(result.rows[0] || {}).map((k) => (
                  <th key={k}>{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((r: any, i: number) => (
                <tr key={i}>
                  {Object.entries(r).map(([k, v]) => (
                    <td key={k}>{String(v)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {result && <Json value={result} />}
    </section>
  );
}
