# Model B / #635：重复研究、表示与信息时钟审计

日期：2026-09-20。审计源码基线：`6e0ff1c9f9b05bf6b023840934f6846c14c85f1d`。
状态：`SOURCE_AUDIT_COMPLETE__NEW_CHAIN_CAUSAL_ACCEPTANCE_PENDING`。

## 1. 承接与去重

历史 v2 已通过 #633/#634 两阶段同步进入 private main `2815f50b5a1b2925f0e0118b0af0d578605ee882`。验收见 `TWO_WAVE_STRATEGY_HISTORY_V2_SYNC_ACCEPTANCE_20260920.*`。
接手时公库 HEAD 与交接一致，仅保留的三个 v2 文件待提交；这些文件被承接而非删除重建。
在新建 #635 前，GitHub 精确标题检索 Model B 和当日 incremental 均无结果；当日 state-exit 仅有已关闭 #624/#625/#627。最新公库未发现 Model B prereg/result；没有重复开工。
#612 仍 open、comments=0，最后更新 2026-09-19，仍是旧 T0 compression economics 任务，不改成当前主线。

## 2. 不是重新做 #429、#615 或 #624

### #429：已有长窗当前上下文条件化研究

该研究使用全部 2015–2020、k=255..70081 的 69,827 个端点，研究 accepted delayed wrapper 的 exact-five-state survival、remaining life 和 opposite-state face-slap。五态 LOW/FINER 跳转包含在 exact-state exit 中。
其 P128/P256 是 raw-price trailing OLS phase，在 k 当时可知；采用 day-cluster bootstrap，比较 ALIGNED/NEUTRAL/OPPOSED 的边际结果。P128 的历史门通过，P256 未过实际幅度门；P128 的 UP/DOWN 不对称同样保留。
它没有在 #624 的 Amendment-A structural target 上，控制 direction、carrier age 和冻结 compression 后做 prior-only 概率 A/B。
所以“当前长窗上下文可能有信息”不是 #635 的新发现；新问题只能是条件增量。

### #615：已关闭的交易经济交互

#615 在 945 个 #507-v2 T0 signals 上，用 stage1 causal_state leg 相对 T0 side 的 ALIGNED/OPPOSED，与固定 LOW/MID/HIGH compression 分组做 own-lifecycle trade-economics interaction。三项核心 bootstrap CI 跨零，NOT_SUPPORTED 保留。
该研究不是 bar-level structural state-exit 概率比较，且其 stage1 causal leg 不是本轮 P128，也不是最终 retrospective C1 residual oracle。
新研究不改它的 bands、不换 cells、不重新宣称 C1 方向可以指导 T0。

### #624：冻结的继承基线

原始 issue 正文不能覆盖 Amendment A。资格仍是 wrapper CURRENT_UP/DOWN，但 primary outcome 是 pre-veto carrier 第一次离开当前方向，不是 LOW/FINER 标签变化。
29,713 rows / 38 blocks、原 score/bands 与 NOT_SUPPORTED 均保留。新 A 是一个增加 direction/age 控制的 prior-only 概率比较层；不能把 A 自身的改善或 B 相对原始裸分数的改善算成 context 增量。唯一核心比较是 B_calibrated 对 A_calibrated。

## 3. 三种表示的身份不可交换

**本轮唯一候选：P128_RAW_PRICE_CURRENT_PHASE。**
复用 `executor/two_wave_postdelay_persistence_v1.py` 的 normalized_ols_drift、parent_phase、directional_relation；文件 SHA256 为 `34fc30211db3922f6ba67b563a05b983fe5780870409fbe3cb39676448389a0f`。
输入是 128 个已完成原生 5m close，窗口 `[k-127,k]`。对 log close 拟合 trailing OLS，用 slope×127 / log-price range 标准化；range<=1e-15 时返回0。阈值仍为 ±0.20。
这只是比冻结64-bar本频视图更长的 raw-price 支持窗口。128 不是已验证的固有周期，不等于 T1=86，不是正交分离的 C1。它混合多个尺度，并与本频64-bar视图有重叠。
选择它是因为 #429 已经对同一 wrapper 做过明确的边际背景研究，公式有限且可逐行核验，因而适合作为最小条件增量复核。这个选择受既有 development 结果启发，不具独立样本选择优势。

**未选：stage1 causal leg。**
#615 实现通过 `continuity_hierarchy(base_inventory(...),1,3)` 的 stage1 与 `_prepare_asof/causal_state` 读取当时 leg；已有 T0 signal 子集前缀证据。它是离散图形/骨架 current-leg 对象，不是 P128，不直接等于显式 C1=S0-S1。本轮不再同时试它来择优。

**未选：final retrospective explicit C1。**
最终完整波/骨架插值带通 oracle 使用事后完成信息；其显著 hindsight 分离不构成 k 时可用 context。#450/R2b 的 LP/BP 历史保留，但不是本轮前置阻塞，也不能把最终残差回填成实时输入。

因此 #635 的正负结论均只适用于这个 P128 表示和这份有限 A/B 合同，不外推为“所有跨频段 context 有效/无效”。

## 4. 时间与延迟

wrapper 的 target time 是 t，knowledge time 是 k=t+8。本轮所有本频特征、carrier age 和 context 的最大信息下标都是 k；未来 outcome 严格从 k+1 开始。
P128 不额外等待未来确认，但 trailing-OLS 可能迟钝、混合长窗内的旧方向，且不能保证某个固定转折延迟。无固定频谱带宽、无跨尺度不变性证明。
原生 bar 按既有交易序列排序，跨午休/隔夜不补零、不插值、不换数据。折年以 knowledge trading_day 为准，不以 t 或任意UTC重解释替代。
旧 P128 源测试覆盖 monotone/flat、relation 和 bootstrap/gate；本次未找到可替代新预测链验收的完整 prefix certificate。因此必须重新测试新链中的 state/features/context/CDF/calibration/prediction，不把继承 wrapper 等同新链通过。

## 5. 标签成熟与截断回放的关键陷阱

仅按 feature.year < test_year 训练不够。拟合第 Y 年模型时，训练标签必须满足 `known_index+8 < first_native_index_of_year_Y`，即整个 +8 窗口在截止点前成熟。
但 label-free compression 的参考分布仍必须使用所有 prior-year eligible decision rows，不能随 supervised-label purge 改动 #624 的 score/cutpoints。
预测入口不能依赖“未来+16已齐”的 evaluation ledger：截断尾端的当时预测应仍可产生。先构建不含 future outcome 的 decision stream，再按冻结 +16 终端支撑选择最终评价集；不可因为 prefix 尾部缺未来标签而改变已知 state、CDF 或预测。

## 6. 当前完成与未完成

完成：历史同步；既有问题与表示身份审计；本轮唯一候选范围与比较层定义。
尚未完成：#635 market coverage、概率拟合、增量评价、全链 market prefix replay、独立 verifier 和 governed receipt。必须先合并对应 prereg，不能把本文当成实证成功。
本线程不修改 private 根 CLOUD_CURRENT，不授予 signal/router/trade/paper/live/production authority。
