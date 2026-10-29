# ResearchAudit 科研实验管家

本地优先 V0.1，所有指标来自导入文件，不附带模拟实验。Python 3.9+ / Node 20+。

## 启动

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
.\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 。开发前端用 npm run dev，代理后端 8000。测试：`.\.venv\Scripts\python -m pytest`。

## 架构与阶段

1. V0.1：FastAPI API、SQLite 不可变采集快照、Polars CSV/Parquet 读取、JSON/TensorBoard/MLflow 指标、Git 与 SHA256、交互曲线、完整性审计、Markdown 证据报告、守恒漂移插件。
2. V0.2：显式实验清单与指标单位/方向/数据划分契约；按模型、数据集和种子分组统计；DuckDB 查询及 Parquet 长表缓存；增量扫描与后台任务。
3. V0.3：收敛阶、敏感性和误差传播插件、可审核论文图模板、Tauri 封装。

backend/collect.py 采集；storage.py 持久化；analysis.py 描述统计和审计；validation.py 插件注册；main.py HTTP；frontend React/TypeScript/Tailwind/Plotly。

## 数据约定与边界

每个相对父目录视为一个实验。config.json 或 params.json 存参数（seed、dataset、split）；metrics.json 支持数值对象或 metrics 字段；CSV/Parquet 数值列转为曲线，最后一个有限观测转为汇总指标。重复列名跨文件目前按扫描顺序覆盖，应使用不同列名或独立实验目录。JSON 不解析 YAML 参数，但仍保存文件哈希。TensorBoard 使用真实 step；CSV 横轴为观测序号。MLflow 支持本地 metrics 文件格式，不连接远端服务。

快照保存导入时的值、相对源路径、SHA256、Git commit、脏工作区状态和采集机器信息；不复制源文件，源文件需自行归档。采集环境不等于原实验执行环境。导入耗时与文件规模相关，当前同步扫描；单文件 256 MiB 上限，跳过会记录。守恒插件通过 POST /api/projects/{id}/validate/conservation?run=...&metric=... 调用。比较 API 提供描述均值和样本标准差，不声称跨实验可比或独立。尚无推断统计和自动异常值判定。Plotly 工具栏支持 PNG 导出。

服务只应绑定 loopback，本地 API 可以读取当前用户有权读取的导入目录，无身份验证。SQLite 位于 .researchaudit，可用 RESEARCHAUDIT_HOME 指定。报告包含绝对项目路径与本地环境信息。DuckDB/SciPy 已列依赖，复杂分析与缓存留后续阶段。

## 更新：指标契约与四级审计

当前版本支持 YAML 配置、幂等快照、最终/最优指标、参数过滤、多种子描述汇总以及 PASS/WARN/FAIL/UNKNOWN 审计。最终值是最后观测，末尾缺失不会静默回退为之前的值。CSV 同名列跨文件冲突会记录并拒绝后者。

每个实验目录的 config.yaml 可声明：

```yaml
seed: 42
dataset: my-dataset
dataset_version: v1
split: validation
evaluation_protocol: evaluation-v1
model_version: baseline-v1
metric_definitions:
  loss:
    direction: minimize
    unit: "1"
    method: mean squared error
```

这些字段是用户声明；相同声明不等于数据集内容已验证相同。缺少可比性字段时结果为 UNKNOWN，不计算跨种子均值。记录完整性、复现执行和科学正确性分别判断。

详细资料：docs/open_source_research.md、docs/architecture.md、docs/implementation_plan.md。运行 `.\.venv\Scripts\python -m pytest -q` 验证受控 TEST DATA；当前 6 项测试通过。前端 `npm run build` 通过，Plotly 包体积仍较大。SVG 导出和显示平滑已加入；PDF 与误差分布图尚未实现。前文旧说明中的“最后有限值”已由这里的最终值规则取代；YAML 参数现在实际解析。

## 图表和证据导出更新

曲线支持后端 PDF/SVG/PNG 导出，另提供观测分布 PDF。每次导出保存图表规格和来源哈希，可通过 /api/projects/{id}/figures 查询；/graph 返回导入证据图。分布图描述选定指标的观测分布，只有输入指标本身是逐样本误差时才可解释为误差分布。

指标缓存写入 Parquet，/observations 接口支持 DuckDB 分页查询。当前仍保留 JSON 曲线，尚未完成大型数据的全链路流式处理。报告增加可读指标和审计表。最新测试 11 项通过，包含真实格式 TensorBoard/MLflow 和图表导出。依赖新增兼容 Python 3.9 的 Matplotlib 3.9.x。

## 历史实验、条件和变量管理

工作台新增历史实验档案，可检索历史参数和补录信息，按标签、审核状态筛选，为每个快照内实验维护条件、变量、依据、标题和备注。每次保存追加修订版本，并检测并发修改冲突；可将旧修订作为新草稿。原始参数和指标保持只读，新采集快照不自动继承旧条件声明。详细操作与 API 见 docs/history_management.md。

## 后台导入任务

界面导入现在后台执行，显示当前文件、任务状态与阶段内计数，并支持取消。取消在文件操作之间生效；进入 committing 后不再取消。服务重启会把未完成任务标记为 interrupted，可重新发起导入。请使用默认单进程启动方式，不使用 uvicorn 多 worker。任务状态保存在本地 SQLite；现有同步导入 API 保留。
