# 公库计算、私库保存与代码回合

本项目采用与多因子双仓标杆相同的三层闭环：Chat负责研究设计、**仅修改配对公库**和控制面决策；已认证controller负责发起公库标准`workflow_dispatch`并跟踪run；本私库固定源码、输入和验收并保存权威结果；公库标准runner执行批准profile；broker自动把结果/失败证据回存本私库run分支和私有Release，controller再回读验签。私库Actions关闭。

本私库不是Chat的直接写面。即使Chat连接器技术上具备本私库写权限，所有本私库变化也必须由配对公库中经审查、固定范围、fail-closed的workflow/broker产生；Chat不得直接修改本私库文件、分支、PR、release或ref。

## 调度控制面

标准研究执行入口是公库`.github/workflows/public-compute.yml`。真实研究run必须满足：公库`staryocean0/csi1000-timing-strategy-public`、分支`cloud-workspace-v1`、事件`workflow_dispatch`、已登记profile。`workflow_dispatch`是事件约束，不要求用户本人点击UI；Chat连接在具备对应动作时可直接调度，或由已认证controller调度。用户UI仅是备用入口。

controller与runner权限分开。controller不使用`FACTORLAB_PRIVATE_TOKEN`、不读取私有数据、不执行研究代码；它只发起/观察标准run。受限私库Secret只进入公库标准workflow的prepare和publish阶段。不得用push/PR/fork直接执行私密研究，不得通过环境变量伪造dispatch事件。

当前会话需要GitHub新能力时，先发现实际工具完整schema。若当前Chat连接没有新建workflow-dispatch动作且当前环境没有已认证controller runtime，记录为控制面运行时缺口并准备controller交接；不能据此否定runner或私库回存通道，也不能默认把用户本人变成常驻controller。

## 通用代码与治理修改后合入私库

在公库独立开发分支修改可公开的通用工具、治理合同和执行器，跑合成测试，审查diff，再合入公库活动分支；记录确切source commit。需要进入本私库的同名通用代码或治理文件，必须由独立的public→private同步workflow处理：固定public source commit、固定private base commit、固定文件映射和内容身份，写入专用本私库分支，逐文件回读验签并创建审查入口。Chat不得直接写本私库完成导入。

科研结果broker的权限保持有界，只写研究run专用分支/Release/receipt；不得把科研broker扩成任意本私库文件写入器。治理/通用代码同步必须使用独立allowlist，不得接受任意路径、任意branch、任意shell或整树覆盖。

私有策略、数据和研究结果只在本私库成为权威记录，但创建/更新动作仍必须来自已冻结公库profile的broker回存或专门同步workflow。任何“先冻结到私库”的步骤都不得绕过这个受控写入面。

## 外部来源仓库边界

中证1000项目只有配对公库/本私库能够拥有项目级current authority。本私库根目录`CHAT_START.md`、`CLOUD_CURRENT.json`及其引用合同定义当前研究锚点。

其他`factorlab-*`仓库只作为source/evidence dependency。它们不得拥有中证1000的`current authority`、`active_research`、canonical BLACKBOX ledger或项目级workflow state。外部仓实验、receipt或BLACKBOX结果在经本双仓控制面固定来源并导入/重放、由本私库回执接受前，只是external evidence。

外部仓若已经打开过outcome/BLACKBOX，数据消费事实仍保留：不得删除失败、重置OOS、把同一窗口包装成fresh验证，或利用隐藏失败原因救阈值/桶/时钟/赢家。

## 已登记profile

- `runtime-smoke`：仅测试公开运行环境、断网和无凭据，不取私有数据。
- `handoff-verify-v1`：固定private commit、五个私有验签源文件与固定交接Release的20个顺序哈希分片；核验2813个包成员，不训练、不重跑策略。
- `risk-v2-severity-persistence-v1`：固定Risk Tool 2.0 Phase-1私有源码、原交接Release和独立verifier；只研究Layer2固定5m Severity × Persistence，不计算PnL，不授予策略路由或生产权限。

每个新研究另行冻结源码、数据范围、命令、资源和验收再注册profile；不能把任意shell或任意private ref变成workflow输入。首次上传、调度成功、prepare/transport成功、compute成功、独立验签、科学结果与生产权限必须分开记录。

## 回存与控制器验收

标准run的取数、计算、清理、回存为独立阶段。只有取数和回存映射受限Secret，计算/清理无凭据。broker在私库写`runs/public-research/<run>-<attempt>`分支、私有Release `public-research-run-<run>-<attempt>`和`research/public-runs/<run>-<attempt>.json`回执；失败run也尽可能回存有界失败证据。

控制器验收只从私库回读已回存结果，重新核对分支回执、Release、bytes/SHA256和独立verifier状态；除非实验协议另行要求，不在controller侧重新执行策略。公库job success不等于科学支持，科学支持不等于生产权限。

公开runner固定ubuntu-24.04，不使用公开artifact/cache，不启用私库Actions，不启用付费larger runner/GPU。用户预算、金融语义、PIT/时钟/复权和已消费年份不能由执行器改变。