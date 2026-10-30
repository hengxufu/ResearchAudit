# ResearchAudit 4.0 开发版使用指南

日期 2026-10-30。这是保留 3.0 功能的增量版本；详细边界见 [验收记录](v4_acceptance.md)。

## 启动

```powershell
cd D:\ResearchAudit
.\.venv\Scripts\python -m pip install -r requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
.\start.ps1
```

访问 http://127.0.0.1:8000 ，交互接口文档为 /docs。只运行一个后端进程。升级前停止服务并备份整个状态目录；外部模型/数据并未复制到状态目录。Linux 命令仍为 `.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`，本轮实测平台为 Windows。

## 接管历史科研目录

在“项目与数据资产”的 Project Intelligence 输入目录并按分析。结构、文件索引、配置参数和共同目录候选来自静态分析；不会运行 train.py、CMake 或 Notebook。大文件和权重默认只读元数据。查看 issues 和 truncated，不完整扫描不能视为完整项目清单。

批量补录将发现目录交给既有采集器，保存真实快照；重复的未变化文件产生相同快照。补录按目录独立提交，批量错误不构成跨目录事务回滚。修正实验关联需填写候选目录、标签和原因，修改保留版本且只标为用户声明。开启持续追踪后，已有 watcher 增量采集新增源文件；项目结构索引本身需重新分析刷新。发现忽略规则与持续追踪规则分别管理。

## 高级统计与科研 Copilot

选择当前快照，在科研分析页填写指标和分组参数。每层至少三个可比较的 Run，独立性须显式声明。选择配对时要求恰好两个条件、相同且唯一的 seed 集；Bootstrap 重采样的是完整 seed 差值而非 epoch。报告记录方法、实验单位、种子、次数和证据。

Copilot 使用当前快照的白名单确定性工具：查询、总结、审计、分析计划。无模型连接也可用，不接受任意代码或 SQL。自然语言查询继承 v3 的有限语法，例如“最好 loss”“哪些实验缺失随机种子”。分析计划不会隐式执行检验。没有通用生成模型/云端连接功能。

## 下一轮优化与真实执行

历史 Run 配置需要明确数值参数、指标方向/单位/方法、数据版本、split 和评价协议。除搜索变量和 seed 外的参数须一致。所有参与的历史参数必须落在声明的有限区间内。

1. 在优化面板填写如 `{"learning_rate":[0.0001,0.01]}`，选择 grid/random/bayesian。界面当前对整个所选快照提出候选；需要筛选/跨快照合并时使用 API refs。
2. 生成候选不会执行代码。贝叶斯模式要求至少三个不同参数位置且目标非恒定；均值、标准差和 EI 仅基于固定核假设，不能当作最优性证明。
3. 填写可信命令 Spec，例如 `{"argv":["python","train.py","--lr","{learning_rate}"],"cwd":"your-project"}`。确保程序实际读取该参数，并将结果写到 RESEARCHAUDIT_OUTPUT_DIR。检查命令后勾选授权，再执行所选候选。
4. 查看实际结果和剩余预算。重复请求复用同一个执行；取消/失败仍消耗已保留候选预算。预算按 proposal 管理，不是跨所有项目的总费用约束。
5. API results 中返回真实 snapshot_id/run_id，将它们加入下一轮 refs 可继续建议；自动执行测试覆盖了这一反馈闭环。当前 UI 候选在页面切换后通过 API 查询历史，尚无完整多轮研究仪表盘。

高级 API 支持线性参数约束，如 `coefficients:{learning_rate:1},upper:0.005`。尚不支持学习输出可行性约束、多目标联合采集函数或自动早停干预。已有 Pareto 分析和执行器超时限制继续可用。

## 环境与复现

项目页面的环境折叠区使用同一个路径输入框填写 requirements.txt 或 Conda YAML。导入仅解析声明，不安装依赖。只对支持的精确版本针脚比较；范围、包含文件、Python/Conda 构建与 channel 等信息保留 unresolved。

新的实际执行记录完整服务 Python distributions；旧记录仍可用。对复现清单调用 `/api/v4/reproductions/{id}/environment-diff` 检查历史服务环境变化，随后继续使用原有复现清单、授权重运行和分维度报告。服务包版本相同不证明目标程序、动态库、CUDA 或科学评价协议一致，容器与跨机器环境自动构建尚未实现。

选择另一解释器时，可向 `/api/v4/reproductions/{id}/target` 提交 `{"executable":"绝对解释器路径"}`。这只派生新清单，不启动程序；父清单版本和输入仍保留。审阅新命令后，向既有 v3 start 接口提交 `confirmed:true,allow_code_change:true` 才重运行。该入口不自动安装目标环境依赖；应通过目标自身的证据与结果比较检查实际差异。

## 图表与仿真

绘图页新增多子图配置，引用真实 MetricRef。可声明尾随平滑窗口、线性/对数尺度和显示 xlim；原曲线始终保留，原数据不变。保存后使用配置 ID 重新生成 SVG/PDF/PNG，响应返回文件 SHA256。置信带和图形模板编辑器尚未完成。

热辐射接口 `/api/v4/science/radiation` 用 K/K/W 源列核验 `P=epsilon*sigma*A*(T^4-Ta^4)`，需指定面积、发射率和容差；输出残差、预测功率、假设与源证据。模型仅适用于指定灰表面/环境且视角因子为1的声明条件。数值通过不等于物理模型有效。原有 Python/C++ 执行、能量积分、收敛、敏感性、线性误差传播和报告功能继续保留。

API 的完整字段、数据库迁移和故障恢复语义见 [架构/API](v4_architecture_api.md)。所有随测试生成的数据均为 TEST DATA，不得作为真实科研发现。
