# 当前尺度主导性：正式诊断测量与阈值无关裁决（2026-09-17）

## 结论

#372 已完成真正的 `workflow_dispatch` 市场诊断测量、独立 verifier 和私有归档验签；随后才将冻结的 raw diagnostics 与此前冻结的192条候选无关参考标签做阈值无关 join。**本轮没有选择任何阈值、分类器、特征权重、迟滞或持续性参数。**

正式 run 为 `35216237190-1`，源码 `ad4458b41d57000731200e39aa5c0539937c7549`。`diagnostics.jsonl` SHA256 为 `aed0b65305f06d36dfd679df4ee75feb48b246a40e3a5e39831cefedf2ee3baa`；192 panels / 960 phase rows。正式 compute 看不到参考标签、future suffix、R1/R2/R3结果或PnL。

冻结标签 SHA256 为 `6fb36ee74413c9b7e95824a94a89bec74a493513668a36b3373c24518fc834be`；阈值无关聚合 join SHA256 为 `bcd47f37b169374b78bfebf230b4aa7537567d8ea92cc55c135ebdba42cc66a8`。192个 opaque panel id 一一匹配；未来60分钟仍未揭示。

## 主要发现

`CURRENT_SCALE_SUPPORTED` 与 `CURRENT_SCALE_NOT_DOMINANT` 的原始证据存在明显秩分离：median tortuosity 的预注册方向 AUC=0.9422，median delta search-adjusted BIC=0.7833，median fractional SSE improvement=0.7767，median normalized RMSE/log-range=0.6900。`DEVELOPING` 与 `NOT_DOMINANT` 在 tortuosity 和 normalized RMSE 上分别达到0.9870和0.9597。

但这些量**不能压成一个单调的 dominance 单分数**。`CURRENT_SCALE_DEVELOPING` 通常是一条更平滑、更接近单腿的未完成结构，因此其 normalized RMSE 和 tortuosity 往往低于已经完成一个宽尺度转折的 `SUPPORTED`。这不是“更强的 dominance”，而是不同的 morphology。

因此当前架构应继续分成至少三个对象：

- morphology / completed-vs-developing 几何状态；
- current-scale dominance evidence；
- 独立 data-validity / outlier guard。

五相位的 shape agreement 在各类中几乎饱和，turn-range 也大多集中在4分钟附近，不能单独承担主分类责任。`DATA_INVALID_EDGE` 的 robust-outlier 中位数只比 SUPPORTED 略高，现有诊断族也不足以独立解决数据有效性。

## 下一门

下一阶段不是直接找一个总分阈值，而应另行预注册 **state/morphology-conditional calibration + separate validity guard**。如果后续需要阈值/迟滞/持续性，必须使用明确的 calibration/evaluation 边界；不能在本次192条参考集上当场挑最优 cutoff，更不能按PnL选择。

R1/R2/R3与旧#321历史结论均不改写；本裁决不授予R4、1m策略、router、信号、交易或生产权限。
