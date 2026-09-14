# Overnight 控制面纠偏记录（2026-09-14）

## 结论

中证1000 Overnight 后续研究必须回到中证1000双仓控制面执行。独立仓 `staryocean0/factorlab-overnight-open-lab` 不再承载本项目的 current authority、active research、canonical ledger 或项目级 workflow state。

中证1000 private 已迁入 Overnight 历史上下文：

`runtime/research/cloud_imports/overnight_open_context/d113b42dca967bb1061c8a6115c5d934e5a41074/`

该迁入快照记录的 Overnight 当前状态为 ledger 12、`active_research=null`，并保留 V6A、B1、B2、C1、C2、B4 等既有连续组件及已关闭下游研究。它是后续 Overnight 研究的历史来源基线；顶层项目 current authority 仍由 private 根目录 `CHAT_START.md` / `CLOUD_CURRENT.json` 决定。

## 外部仓发生过的越界研究

此前 Chat 在独立 `factorlab-overnight-open-lab` 中把 extreme-open 条件化研究错误地升级成了中证1000项目式的 authority/ledger/workflow。该仓的这些治理变更不属于中证1000双仓权威链。

但已经发生的 outcome exposure 不能假装没有发生。需要保留的低带宽事实只有：

- external repository：`staryocean0/factorlab-overnight-open-lab`
- authorized-main checkpoint：`308a9c700abe66cf09c6c3a6429e03563a0507fd`
- result branch：`research/overnight-extreme-p5-result`
- result commit：`4f600aa4338937a377b08ef5d5c70fed6884dee1`
- external query identity：`overnight_extreme_open_callable_state_reusable_validation_v1`
- external query id：`b9ab7b709b5667456a0d`
- low-bandwidth decision：`FAIL`
- state-level metrics/counts/years/failure attribution：not persisted / not authorized
- external draft PR #24：不得作为中证1000项目 closeout 合并依据

该 `FAIL` 只能登记为 **external consumed negative evidence**：它证明同一 identity 已经接触过 2021-2025 reusable window，因此该窗口不得再被包装成 fresh OOS。因为协议没有保存状态级失败归因，也不得通过拆包、删状态、改阈值、改时钟、挑赢家或三重交叉来“救”这一 exact identity。

## 对科学结论的处理

1. 不把外部仓 P1-P5 governance/ledger 直接搬成中证1000 official authority。
2. 不删除外部失败结果，不重置其数据消费事实。
3. 不把 external P5 FAIL 解释为 B1/B2/B4 等连续因子失效；它只针对外部六状态整包 identity。
4. 如果未来需要在中证1000双仓内研究新的 Overnight 条件组件，必须重新冻结一个独立研究身份、动机、输入边界和 DEV/validation 合同；不得利用外部 FAIL 的隐藏原因做参数救援。
5. 后续所有 Overnight 代码执行、数据读取、结果回存均注册为中证1000 public profile，由 public runner + broker 执行并回存 private。

## 工程纠偏

本次公库治理修复新增 fail-closed 规则：

- Chat 只修改 public；
- private 只通过 public 受控 workflow/broker 变化；
- external FactorLab 仓只读作为 source/evidence；
- 科研 result broker 不扩权为任意 private 文件写入器；
- 治理/通用代码同步使用独立固定路径 allowlist。

在 private 对应治理文本经受控同步接受前，本文件是 public 侧的纠偏提案和证据索引，不宣称已经改写 private current authority。