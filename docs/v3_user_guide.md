# ResearchAudit 3.0 使用指南 / User guide

这是 3.0 开发迭代。完整验证范围、未完成项和测量条件见 [验收记录](v3_acceptance.md)，API 字段见 [接口契约](v3_api.md)。

## 安装与启动

```powershell
cd D:\ResearchAudit
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
.\start.ps1
```

访问 `http://127.0.0.1:8000`，API 交互文档为 `/docs`。只启动一个后端进程。现有 `.researchaudit` 数据直接保留，v3 增量建表；升级前停止服务并备份整个状态目录。若使用自定义 `RESEARCHAUDIT_HOME`，备份该目录。外部数据资产仍在原始路径，状态目录备份不包含它们。

Linux: `.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`。当前交付的实际测试运行在 Windows；Linux CI 定义保留，但未观察到本轮远程执行结果。

## A. 训练记录、历史复现和验证报告

1. 在“实验执行中心”输入已有工作目录、JSON 命令数组及参数。创建只保存 Pending；检查后按 Start 才执行。程序应将待采集指标写到 `RESEARCHAUDIT_OUTPUT_DIR`。导入历史目录不会执行其中的代码。
2. 要执行随仓库提供的受控例子，命令为 `["D:\\ResearchAudit\\.venv\\Scripts\\python.exe","D:\\ResearchAudit\\examples\\TEST_DATA_train.py"]`，工作目录为 `D:\ResearchAudit`。**该文件是测试用数据训练程序**，使用 NumPy 实际训练两层 tanh 网络，生成 40 次 MSE 观测及权重 NPZ；不代表真实科研数据，也不等同于 PyTorch/CUDA 认证。
3. 通过执行参数/API 记录 `seed,dataset,dataset_version,split,evaluation_protocol`，以及 `metric_definitions.loss={direction:"minimize",unit:"1",method:"MSE"}`。同一个运行的声明会保存到执行输出配置。已有历史数据如果没有授权执行记录，先导入和审计；本轮不会猜测原始启动命令。
4. 成功执行后，在 Experiment reproduction 选择源执行，输入各指标的 `atol/rtol`。可填写已捕获的数据集/模型资产版本 ID（逗号分隔），下载机器可读清单。
5. 检查清单中的命令、cwd、入口源码范围、Git、环境范围和输入版本，勾选授权，按 Replay。若代码/Git/已哈希输入变更，默认拒绝。API 的 `allow_code_change:true` 仅用于经过研究人员审阅的差异重运行，报告保留该记录。
6. 重运行完成后按 Evaluate。报告分别显示环境完整性、数据可获取性、执行成功性、结果一致性、证据完整性；缺失数据为 UNKNOWN。下载 JSON 复现报告。容差缺失、评价定义缺失或数据协议不匹配的指标不会 PASS。

复现清单保存当前已声明的入口文件和 Git 补丁，不会自动 checkout、安装依赖或恢复外部输入；完整环境封存仍是后续工作。非确定性结果可以通过 `/api/v3/reproductions/distribution` 比较独立 Run 分布，非显著差异不构成等价性证明。

## B. 多模型分析、诊断与科研总结

在每个实验目录保存 CSV/JSON/TensorBoard 指标和 config.yaml/json。配置示例：

```yaml
seed: 7
model_version: baseline
dataset: my_dataset
dataset_version: sha256-or-declared-release
split: validation
evaluation_protocol: mse-v1
metric_definitions:
  loss: {direction: minimize, unit: '1', method: mean squared error}
```

导入后在顶部选择快照。“科研分析”保留描述统计、多随机种子分组、配对/独立检验、相关分析。相同评价口径是比较前提；不同域可以分别分析，不能默认为可直接排序。

新增诊断面板输入明确的损失指标、窗口和阈值。只对声明 minimize 的损失运行趋势规则；波动、停滞、上升或训练/验证反向变化是描述性线索。每条规则返回输入、观测、条件及源文件。训练历史列出最佳观测、候选检查点和真实执行时长；最佳观测与某个权重文件的关系仍需独立记录。

总结实验时多选 Run，可得到参数差异、原始最终值、可比性、缺失项和待验证假设。不会生成虚构显著性或因果结论。自然语言查询只支持可检查语法，例如“哪些实验没有记录随机种子”“最好 loss”；指标名必须精确，排序方向来自指标定义。问答范围为当前快照。

“科研绘图”和“报告与成果”继续支持真实曲线/分布、SVG/PDF/PNG、来源清单和独立校验 ZIP。平滑仅显示，不修改观测。新增结果可由证据图追踪到分析和源数据。

## C. 数据浏览与科学仿真

在“项目与数据资产”先注册本地目录或文件，再到 Research Data Studio 刷新资产。

- 选择文件、检查结构。CSV/Parquet/JSON 使用偏移分页；大 CSV 的深分页仍需扫描。
- HDF5/NPY/NPZ 选择字段，输入每维 `[start,stop,step]`，按 Read slice。切片均值只描述切片；上限为 100,000 个元素、8 MiB 原始数值。NPZ 不是任意大文件的懒解压方案，单成员上限 64 MiB。
- 图像显示本地缩略图；权重只显示元数据，不执行 pickle。Notebook 文件只导入已有文本/JSON 输出，原始代码不运行，HTML 不渲染。
- 需要版本完整性时显式捕获 full hash 并验证，预览本身不是完整性证书。

在分析页选择 Run，展开 Simulation equations，填写能量、净功率、时间列，明确 J/W/s 及绝对/相对容差。检查方程为 `E(t)-E(0)-∫P_net dt=0`，必须提供全部净功率项。闭系统漂移、网格/时间步收敛和单参数敏感性不得混淆。

`examples/TEST_DATA_simulation.cpp` 为受控 C++ 能量数据样例。Windows MinGW 可使用 `g++ -std=c++11 -static -static-libgcc -static-libstdc++ examples/TEST_DATA_simulation.cpp -o <your-test-output>/simulation.exe` 构建，避免混用本机动态 C++ 运行库。ResearchAudit 运行已有可执行文件，不自动编译导入源码。编译路径须由用户选择；测试仅在临时测试目录构建。

网格收敛/敏感性从 Run 的两列真实数据读取，要求配置明确单位。位姿计算必须填写真值/预测各四个四元数列、三个平移列、四元数顺序、旋转约定、同一坐标系及平移单位。可选失败阈值产生源行索引；不自动进行样本 ID 重排或约定转换。分类失败样本继续使用 `sample_id,target,prediction` 源表及已有质量接口。

## D. 工作流、版本和报告

在实验执行中心的 Workflow Studio 使用导入报告模板，或 Add node 创建节点。修改节点类型、配置、依赖多选和重试次数。每次保存产生新版本；运行绑定该版本，运行中编辑不会改变已启动的定义。

导入模板需要填写 import 节点的真实路径和 figure 的指标名。添加 command 节点时配置为现有执行 Spec（argv 数组、cwd 和可选资源限制），不使用 shell 字符串。

节点输出引用例子：`{"$ref":"train.snapshot_id"}`，统计节点可用 `{"$ref":"train.runs.0.run_id"}`。所有引用必须来自直接依赖。`runs.0` 由研究人员明确选择，不自动推断实验归属。

条件例子：`{"node":"train","path":"runs.0.metrics.loss","op":"lt","value":0.2}`。条件只读取保存的输出，禁止 eval。重试次数 1 表示初次失败后再试一次；会重新运行命令，因此应由研究人员确认重试不会覆盖外部重要文件。

检查流程后勾选授权，再按 Run workflow。界面显示每节点状态/次数，Inspect 查看输入输出错误，导出节点可直接下载图或 PDF。取消只作用于本工作流拥有的命令。服务重启将未完成流程标记 Interrupted，不会自动重跑。复杂示例在 [workflow_templates](workflow_templates)。

## 科研知识与结论证据

在“证据图谱”下新建 note/hypothesis/design/claim/issue/milestone，填写条件。支持证据与冲突证据分别使用 snapshot/analysis/figure/knowledge 引用；可一键关联当前快照。保存保留修订历史并拒绝过期修订覆盖。默认 unverified；证据链接存在不等于结论被证实。全文检索为本地最新版本 JSON 文本检索。

所有控制样例和基准均标记 TEST DATA；不要将其结果写成真实科研结论。
