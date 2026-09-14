# 公库计算、私库保存与代码回合

本项目按多因子双仓标杆的同一三层闭环运行：Chat负责研究设计、**仅限公库的修改**和控制面决策；已认证controller负责发起公库标准`workflow_dispatch`并跟踪run；私库冻结源码、输入和验收并保存权威结果；公库标准runner执行批准profile，broker在运行结束后自动回存私库run分支和私有Release。私库Actions关闭。

这里的核心不是“公私库都能被Chat写”，而是**公库是Chat修改面与执行控制面，私库是受控写入后的权威存储面**。即使连接器技术上暴露私库写动作，Chat也不得直接修改私库；私库变化必须由公库中经审查、固定路径、固定输入、fail-closed的workflow/broker产生，并接受回读验签或私库治理验收。

## 调度控制面

`.github/workflows/public-compute.yml`是唯一标准私密研究执行入口，实际研究run必须是`workflow_dispatch`、固定`cloud-workspace-v1`、固定白名单profile。`workflow_dispatch`是GitHub Actions事件类型，不意味着必须由用户本人在网页点击：标杆仓允许Chat连接在暴露该动作时直接调度，也允许独立、已认证的controller调度；GitHub UI只是备用入口。

controller与runner身份必须分开。controller只负责发起和观察标准run，不持有公库`private-research`环境中的`FACTORLAB_PRIVATE_TOKEN`，不读取研究数据、不运行私有研究代码、不伪造run事件。受限私库凭据只在标准workflow的prepare/publish步骤出现。不得用push、PR、fork或修改`GITHUB_EVENT_NAME`替代真正的`workflow_dispatch`。

当前Chat连接器是否暴露“新建workflow dispatch”必须按会话实时发现，不能由仓库文档假定。若当前连接器缺失该动作，应记录为**控制面运行时能力缺口**；这不否定GitHub文件读写、公共runner、私库Secret或broker回存能力。标杆多因子仓的已验证闭环曾由独立本地controller调度标准workflow，再由Chat/控制器回读私库结果。本仓沿同一身份边界，不把用户本人点击UI定义为架构必需步骤。

## 通用代码和治理修改如何进入私库

在公库独立开发分支修改可公开的通用工具、治理合同和执行器，跑合成测试，审查diff，再合入公库活动分支；记录确切source commit。需要进入私库的同名通用代码或治理文件，不由Chat直接写私库，而由**独立、窄范围的public→private同步workflow**处理：固定公库source commit、固定私库base commit、固定文件映射与SHA256，创建专用私库分支，逐文件回读验签，并生成可审查回执。同步workflow不得获得任意私库路径、任意branch、任意shell或整树覆盖权限。

私有策略与研究结果也只在私库成为权威记录，但其创建/更新必须由已冻结研究profile的broker回存或专门同步workflow完成。任何“先冻结到私库”的步骤都必须通过这个受控写入面实现，不能用Chat直接修改私库来省略控制面。

现有科研结果broker的写入范围保持不变：它只负责研究run结果、私有Release和`research/public-runs/...`回执。**不得为了治理同步而把科研broker扩成任意私库文件写入器。** 治理/通用代码同步必须使用独立实现和独立allowlist。

## 外部来源仓库边界

中证1000项目只有这一对仓库可以拥有项目级current authority：公库是执行/同步控制面，`staryocean0/csi1000-timing-strategy-private`是权威研究状态与结果存储面。私库`CHAT_START.md`、`CLOUD_CURRENT.json`及其引用的冻结合同定义当前研究锚点。

其他`factorlab-*`仓库可以作为历史证据、工具来源或待导入代码来源，读取时记录固定repo/ref/commit/文件哈希；它们不得拥有本项目的`current authority`、`active_research`、canonical BLACKBOX ledger或项目级workflow state。外部仓中的实验、receipt或BLACKBOX结论，在经本双仓控制面固定来源并导入/重放、由私库回执接受之前，只是**external evidence**，不能自动成为中证1000科学结论。

若历史工作曾在外部仓越过该边界，应保留其提交和失败结果，不继续在外部仓扩展中证1000治理；在本公库建立纠偏/导入合同，通过受控workflow把需要保留的代码或低带宽结论带回私库。禁止根据外部BLACKBOX隐藏行为做阈值、桶、时钟或赢家救援。

## 已登记profile

- `runtime-smoke`：仅测试公开运行环境、断网和无凭据，不取私有数据。
- `handoff-verify-v1`：固定private commit、五个私有验签源文件与一个固定压缩包的20个顺序哈希Release分片；在无网络、只读输入、4CPU/12GiB容器核验2813个包成员，由另一个只读验证步骤复核。它不训练、不重跑策略、不读取未来收益选参。
- `risk-v2-severity-persistence-v1`：固定Risk Tool 2.0 Phase-1私有源码、原交接Release和独立verifier；只研究Layer2固定5m `Severity × Persistence`，不计算PnL、不授予策略路由或生产权限。

初始交接验签通过后，每个新的策略研究另行固定源码、数据范围、命令、资源和验收再注册profile；不能把任意shell或任意private ref变成workflow输入。首次上传、调度成功、prepare/transport成功、compute成功、独立验签、科学支持与生产权限是不同状态。

## 自动私库回存

标准workflow启动以后，取数、计算、清理、回存为独立阶段。只有取数和回存映射受限Secret，计算/清理都不携带。broker在私库创建`runs/public-research/<run>-<attempt>`结果分支，将完整结果包写入私有Release `public-research-run-<run>-<attempt>`，并写`research/public-runs/<run>-<attempt>.json`回执；失败run也应尽可能回存有界失败证据。控制器随后从私库重新读取回执/Release做独立验签，不能把公库job显示success单独当成科学通过。

公开工作流固定标准`ubuntu-24.04`，无公开artifact/cache。公库自己的`GITHUB_TOKEN`只服务本公库，不等于私库授权；`FACTORLAB_PRIVATE_TOKEN`只存在`private-research`环境并受分支策略限制。

费用核对：本设计只使用公库标准GitHub-hosted runner，不启用私库Actions、不启用larger runner/GPU。金融结论、数据资格、样本外身份和用户预算不能由执行器自行改变。