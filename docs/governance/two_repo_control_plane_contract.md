# 中证1000双仓控制面合同

## 1. 唯一控制面

本项目只有一对活动仓库：

- public：`staryocean0/csi1000-timing-strategy-public`
- private：`staryocean0/csi1000-timing-strategy-private`

public 是 Chat 可修改的公开执行、同步和治理开发面；private 是源码版本、冻结研究状态、私有数据清单、研究结果和验收回执的权威存储面。private Actions 保持关闭。

Chat-visible GitHub mutation 只允许发生在 public。即使连接器技术上暴露 private 写权限，Chat 也不得直接创建、修改、删除、合并或移动 private 的文件、分支、PR、release 或 ref。

## 2. private 如何变化

private 的变化只能由 public 中经审查的受控 workflow/broker 发起，并满足：

1. `workflow_dispatch` 或另有明确冻结的非研究治理事件；不得用 push/PR/fork 直接执行私密研究。
2. 固定 public source commit。
3. 固定 private base commit。
4. 固定文件映射或固定研究 profile；不得接受任意路径、任意 private ref、任意 shell。
5. 写入 private 专用分支，不整树覆盖。
6. 写后逐文件回读并核对 bytes/SHA256。
7. 研究结果与治理/通用代码同步使用不同 allowlist；科研结果 broker 不升级为任意 private 文件写入器。
8. production authority 默认且持续为 `false`。

## 3. 研究执行闭环

标准私密科研闭环：

`Chat研究设计/公库修改 -> controller调度public workflow_dispatch -> broker从private固定commit取固定输入 -> 无凭据断网计算 -> 独立verifier -> broker回存private专用分支/Release/receipt -> controller或Chat只读回验 -> private权威状态接受`。

公库 job success、transport success、compute success、verifier success、scientific support、consumer utility 和 production authority 必须分开记录。

## 4. 外部仓库边界

`factorlab-*` 等其他仓库只能作为 source/evidence dependency。读取必须记录固定 repository、commit/ref 和必要文件哈希。

外部仓库不得拥有中证1000项目的：

- current authority；
- `active_research`；
- canonical BLACKBOX ledger；
- 项目级 workflow state；
- “已合入/已验收中证1000”的完成声明。

外部实验或 receipt 在经本双仓控制面固定来源并导入/重放、由 private 回执接受前，只是 external evidence。

如果外部仓已经执行过 outcome-bearing/BLACKBOX 查询，即使它不具备中证1000项目 authority，该数据暴露仍必须按已消费处理；不得删除失败、不得重置 OOS、不得把同一窗口重新包装成 fresh 验证，也不得依据隐藏失败归因做 successor rescue。

## 5. Overnight 的特例

private 已存在迁入快照：

`runtime/research/cloud_imports/overnight_open_context/d113b42dca967bb1061c8a6115c5d934e5a41074/`

它是中证1000 Layer2 开盘连续属性的正式历史上下文来源。该快照自身不是当前项目顶层 current authority；顶层 current authority 仍由 private 根目录 `CHAT_START.md`、`CLOUD_CURRENT.json` 及其冻结研究合同决定。

独立仓 `staryocean0/factorlab-overnight-open-lab` 自本合同起只作为历史/来源仓读取，不再承载中证1000项目的新 authority、ledger 或执行状态。