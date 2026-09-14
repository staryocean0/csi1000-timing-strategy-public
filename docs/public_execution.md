# 公库计算、私库保存与代码回合

本项目按多因子双仓标杆的同一三层闭环运行：Chat负责研究设计、仓库修改和控制面决策；已认证controller负责发起公库标准`workflow_dispatch`并跟踪run；私库冻结源码、输入和验收并保存结果；公库标准runner执行批准profile，broker在运行结束后自动回存私库run分支和私有Release。私库Actions关闭。

## 调度控制面

`.github/workflows/public-compute.yml`是唯一标准私密研究执行入口，实际研究run必须是`workflow_dispatch`、固定`cloud-workspace-v1`、固定白名单profile。`workflow_dispatch`是GitHub Actions事件类型，不意味着必须由用户本人在网页点击：标杆仓允许Chat连接在暴露该动作时直接调度，也允许独立、已认证的controller调度；GitHub UI只是备用入口。

controller与runner身份必须分开。controller只负责发起和观察标准run，不持有公库`private-research`环境中的`FACTORLAB_PRIVATE_TOKEN`，不读取研究数据、不运行私有研究代码、不伪造run事件。受限私库凭据只在标准workflow的prepare/publish步骤出现。不得用push、PR、fork或修改`GITHUB_EVENT_NAME`替代真正的`workflow_dispatch`。

当前Chat连接器是否暴露“新建workflow dispatch”必须按会话实时发现，不能由仓库文档假定。若当前连接器缺失该动作，应记录为**控制面运行时能力缺口**；这不否定GitHub文件读写、公共runner、私库Secret或broker回存能力。标杆多因子仓的已验证闭环曾由独立本地controller调度标准workflow，再由Chat/控制器回读私库结果。本仓沿同一身份边界，不把用户本人点击UI定义为架构必需步骤。

## 通用代码修改后合入私库

在公库独立开发分支修改可公开的通用工具，跑合成测试，审查diff，再合入公库活动分支；记录确切source commit。随后在私库独立分支按文件清单导入，核对双方同名文件差异后逐段合并，保留旧冻结源码。私有策略改动直接在私库完成；不得为“先公后私”公开私密策略。最终以私库PR或明确回执接受，不覆盖全部runtime。

## 已登记profile

- `runtime-smoke`：仅测试公开运行环境、断网和无凭据，不取私有数据。
- `handoff-verify-v1`：固定private commit、五个私有验签源文件与一个固定压缩包的20个顺序哈希Release分片；在无网络、只读输入、4CPU/12GiB容器核验2813个包成员，由另一个只读验证步骤复核。它不训练、不重跑策略、不读取未来收益选参。
- `risk-v2-severity-persistence-v1`：固定Risk Tool 2.0 Phase-1私有源码、原交接Release和独立verifier；只研究Layer2固定5m `Severity × Persistence`，不计算PnL、不授予策略路由或生产权限。

初始交接验签通过后，每个新的策略研究另行固定源码、数据范围、命令、资源和验收再注册profile；不能把任意shell或任意private ref变成workflow输入。首次上传、调度成功、prepare/transport成功、compute成功、独立验签、科学支持与生产权限是不同状态。

## 自动私库回存

标准workflow启动以后，取数、计算、清理、回存为独立阶段。只有取数和回存映射受限Secret，计算/清理都不携带。broker在私库创建`runs/public-research/<run>-<attempt>`结果分支，将完整结果包写入私有Release `public-research-run-<run>-<attempt>`，并写`research/public-runs/<run>-<attempt>.json`回执；失败run也应尽可能回存有界失败证据。控制器随后从私库重新读取回执/Release做独立验签，不能把公库job显示success单独当成科学通过。

公开工作流固定标准`ubuntu-24.04`，无公开artifact/cache。公库自己的`GITHUB_TOKEN`只服务本公库，不等于私库授权；`FACTORLAB_PRIVATE_TOKEN`只存在`private-research`环境并受分支策略限制。

费用核对：本设计只使用公库标准GitHub-hosted runner，不启用私库Actions、不启用larger runner/GPU。金融结论、数据资格、样本外身份和用户预算不能由执行器自行改变。
