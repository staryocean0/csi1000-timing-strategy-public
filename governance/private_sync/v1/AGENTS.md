# 中证1000择时策略：私有研究控制面

先读CHAT_START.md、CLOUD_CURRENT.json、docs/LAYERS.md、docs/DATA_POLICY.md和docs/WORKFLOW.md。
本仓是文件、源码版本、数据清单和结果的权威存储；数据大包在本私库Release。原多因子两库的已通过结论属于其自身；本库状态以本库回执为准，不继承旧run的ready。

当前研究主线是Layer2 Risk Tool 2.0固定5m `Severity × Persistence`。历史Layer3 `runtime/tmp/csi1000_1m_risk_bucket_probe_20260913`保留为前置证据，不继续按LAT P搜风险阈值。具体当前状态以CHAT_START.md和CLOUD_CURRENT.json为准。

## 执行与信息边界

本项目必须与`factorlab-multifactor-stock-lab` / `factorlab-multifactor-research-private`标杆保持同一三层闭环：Chat负责研究设计、**仅修改配对公库**和控制面决策；已认证controller负责发起公库标准`workflow_dispatch`并追踪run；公库标准runner执行冻结profile；broker自动把结果和失败证据回存本私库分支/私有Release；controller再从私库回读验签。私库Actions关闭。

**本私库是权威存储面，但不是Chat的直接写面。即使当前GitHub连接技术上具备本私库写权限，Chat也不得直接创建、修改、删除、合并或移动本私库文件、分支、PR、release或ref。** 所有需要进入本私库的通用代码、治理文件、冻结合同、研究结果和回执，必须由配对公库中经审查、固定路径、固定输入、fail-closed的workflow/broker写入专用分支，并接受回读验签或本私库治理流程。

“只允许workflow_dispatch”是**研究run的事件边界**，不是“必须由用户本人点击GitHub UI”。若当前Chat GitHub连接原生暴露新建workflow-dispatch动作，可由Chat直接调度；若当前会话挂载了已认证controller，则由controller调度；用户UI只是备用入口。不得因为某次Chat连接缺少dispatch动作，就把用户本人永久写成架构中的日常调度器。

不得增加push、pull_request、pull_request_target、fork或其他事件直接执行私密研究，也不得伪造`GITHUB_EVENT_NAME`绕过broker上下文门。controller与runner身份分离：controller不使用公库`private-research`环境中的`FACTORLAB_PRIVATE_TOKEN`，不读取私有数据、不运行研究代码；受限Secret只由标准workflow的prepare/publish阶段使用。

公库仅放经审查可公开的通用执行器、治理合同和基础设施修改。私有策略、数据、研究结果只在本私库成为权威记录，但**写入动作必须由公库受控workflow/broker完成**，Chat不得直接写本私库研究分支。通用代码在公库修改后记录固定公库commit，逐文件审查再由受控同步流程导入本私库；不得整树覆盖Layer1—4或旧冻结原件。没有权限的工具不能靠AGENTS获得权限；不同会话/插件版本暴露的GitHub动作可能不同，每次需要新操作时先重新发现实际工具，不能继承旧会话的永久能力结论。

每个新研究任务必须先冻结目标、代码提交、允许文件、数据角色、命令、资源上限、输出和验收，再注册单独公库profile。需要成为本私库权威文件的冻结合同，应先在公库完成审查，再由固定治理同步workflow写入本私库并回读验签；**不得用Chat直接写本私库来完成“先冻结”。** 禁止任意shell、任意私库路径/branch或任意runner输入。科研broker只拥有固定研究结果回存范围，不得扩成任意本私库文件写入器。

## 控制面唯一性与外部仓边界

中证1000项目只有这一对仓库可以拥有项目级current authority：配对公库承担公开执行/同步控制面，本私库承担权威研究状态与结果存储。根目录`CHAT_START.md`、`CLOUD_CURRENT.json`及其引用的冻结合同定义当前研究锚点。

`factorlab-*`等外部仓库可以作为历史证据、工具来源或待导入代码来源读取，并且必须记录固定repo/ref/commit/文件哈希；**外部仓不得为中证1000项目创建或持有current authority、active_research、canonical BLACKBOX ledger、项目级workflow state或“已合入中证1000”的完成声明。** 外部仓中的实验、receipt或BLACKBOX结论，在经本双仓控制面固定来源并导入/重放、由本私库回执接受之前，只是external evidence，不能自动成为本项目科学结论。

如果外部仓已经执行过outcome-bearing或BLACKBOX查询，即使其控制面归属错误，该数据暴露仍按已消费处理：保留失败，不重置OOS，不把同一窗口重新包装成fresh验证，也不使用隐藏失败归因做阈值、桶、时钟或赢家救援。

当前Chat若没有workflow-dispatch动作，同时当前执行环境也没有已认证controller runtime，应精确记录为“控制面运行时缺口”，并按`docs/ops/cloud_local_communication.md`给出固定profile、public commit、private commit和验收要求的controller交接。不得把这个缺口扩大解释为公库runner不可用、私库授权失败或双仓闭环设计无效；也不得以push私密任务作为替代。若交接文档本身需要更新，也由公库治理同步workflow写入本私库，Chat不直接修改。

所有已消费年份保持已消费，上传不产生fresh OOS。数据未覆盖、模型无效、工程接收、下游策略效果、生产权限分开判断。禁止用模拟测试或文件存在声称真实策略回测已通过。保留亏损研究与所有冻结版本，不force-push、不改写历史、不批量删除。

文本使用文本接口，PDF/Parquet/ZIP使用Git/REST原始字节；1—100MB Contents返回空content不是普通写权限问题。源和目标分别核验bytes/SHA256，不能跨仓直接引用未在目标创建的Git blob。收到平台安全拒绝先自审请求，不能编码、换路径或换接口绕过；没有原因就记录unknown，不声称所有历史拦截已解决。

DeepSeek禁用，Luna/Terra/Spark仅当前用户明确请求；不使用Auto/Fast或退休工作流。云端缺数据或缺controller运行时时，按docs/ops/cloud_local_communication.md准备最小可执行交接，不能默默补数、自动下载全本地仓或用别的年份冒充；Chat只在公库准备交接源，私库版本由受控同步流程产生。

## 仓库操作被拒绝后的助手自审规则

仓库修改内容由执行助手生成时，排查责任首先属于助手，不应把“为什么被拒绝”直接丢给用户。收到平台安全拒绝或其他无提交结果后，先停止该次写入并重新审查自己准备的动作、目标和内容。

自审至少检查：目标公私库是否正确；**是否正在直接写私库或把外部来源仓误当成本项目控制面**；是否意外携带凭据、下载授权参数或不必要的私有研究内容；读取、诊断、执行和发布是否被错误地耦合为一个过宽动作；代码是否暴露任意执行、过宽文件/网络访问、批量破坏或与任务无关的权限；路径、分支、文件SHA、接口和二进制/文本类型是否匹配；是否有默认把未知状态当通过、把计划写成已完成、将未测试代码称已验收等实现或证据错误；金融、PIT、时钟、复权、数据缺失及样本外语义是否与现行合同一致。

发现具体问题时，助手应自行做实质修正：缩小职责和权限，删除不必要能力或敏感信息，修正逻辑、接口与完成声明，补合成反例、测试或远端回读，然后把修订后的正常任务重新提交。用户不需要替助手猜哪一段代码或文档应该怎样改。措辞或结构调整应服务于正确性、最小范围和清晰职责，而不是只做同义替换来碰平台规则。

如果完整自审后没有找到可证实的问题，或者实质修正后的独立请求仍被拒绝，则如实保存平台返回、目标、时间和未提交状态；不反复变换措辞、编码、路径或接口碰运气，也不无依据要求用户增加权限。可以继续推进与该拒绝无关的合规任务，由用户另行研究平台侧原因。

一次修订后成功，只说明修订版本及其范围已经被接受，不能单独证明此前由某个关键词触发。无论平台是否给出具体原因，助手都必须先完成对自己生成内容的代码质量、范围、信息暴露和证据声明审查，再决定下一步；能由助手修正的问题应由助手修正并继续完成任务。