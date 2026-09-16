# 本频段周期可识别性 × C2 位置：正式裁决（2026-09-16）

正式标准 run：`35084682048-1`；source `0e98f6bfa67b8a0c1e040fb69beeaa479d6f5d88`；profile `two-wave-cycle-identifiability-v1`。prepare、断网无凭据 compute+verifier、cleanup、private publish 均成功。输入仍是已消费 000852.SH 5m 2015–2020 Development；没有 1m、没有收益/PnL、没有训练。

## 核心结果

冻结本级 T0 为 21 bars。70,114 根 bar 中，完整 base 波 occurrence 几何覆盖 58,468 根（83.39%），未覆盖 11,646 根（16.61%），形成 146 个连续盲区。

这些盲区几乎不是“小振幅噪声”：

- 144/146（98.63%）属于 `RESET_ROOT_BREAK`；仅首端/末端各 1 个截断盲区。
- 按已完成 base 波振幅经验四分位比较，126/146（86.30%）是 Q4，15 个 Q3、5 个 Q2、**0 个 Q1**；Q3+Q4 合计 96.58%。
- 盲区长度中位 72 bars，即 3.43×T0；90 分位 111 bars，即 5.29×T0。
- raw high-low log range 中位约 0.0335，绝非只有微小振荡才被拒绝。

因此本轮直接否定了“当前主要只是因为振幅太小所以看不出周期”这个解释。冻结识别器存在大量**有实际价格幅度、但在 root/reset 边界没有被分配为完整波**的结构。

## 为什么这轮还不能回答“是否集中在 C2 底部横盘”

这一步恰恰暴露了更深的表示问题。retrospective C2 使用现有 hard-root hierarchy 的 46 个完整 C2 波。所有已解析的 C2 UP/RANGE/DOWN × rising/falling leg × early/middle/late cell 中，blind bars 都是 0；与此同时，146 个盲区全部是 `C2=UNRESOLVED`。

这**不能**解释为“盲区不发生在 C2 的任何阶段”。真实含义是：造成 base 盲区的 lower-level root break 同时让现有 C2 carrier 在这些位置断掉，因此我们连“这些盲区物理上处在完整 C2 的哪个位置”都没有一个连续的数学坐标系。

所以用户提出的“是不是大级别底部横盘时，本级周期尤其难识别”仍是一个有效问题，但**当前 hard-root C2 数学对象没有资格回答它**。如果强行用现有 C2 已解析区做 retrospective 对照，会形成选择偏差：恰好把最需要研究的断裂区全部排除。

## Causal as-of 地图给了什么信息

在 C2 当时确实可解析的区域里，共有 12,674 个 causal C2 bars。base wave confirmation density 在不同 descriptor / leg / phase / amplitude cell 之间有明显差异；部分 late 或 middle cell 在最近一个 T0 内没有新 base confirmation 的比例超过 30%–44%。例如：

- C2 `UP`、当前 `DOWN` leg、`LATE`、Q1：200 bars，最近 T0 无 base confirmation = 44.0%。
- C2 `DOWN`、`DOWN` leg、`MIDDLE`、Q3：133 bars，39.10%。
- C2 `DOWN`、`UP` leg、`LATE`、Q4：384 bars，36.98%。
- C2 `UP`、`UP` leg、`LATE`、Q1：921 bars，33.44%。

但这些差异并没有形成一个跨 descriptor/leg/amplitude 都单调一致的“某个 C2 phase 必然失明”规律。本轮没有预注册统计模型去从 53 个不均衡 cell 中挑赢家，因此不能看到几个高比例 cell 就宣布一个状态信号。

## 裁决

1. **主要失明不是小振幅。** substantial-amplitude blind episodes 大量存在。
2. **主要观察到的失败模式是 root fragmentation。** 146 个盲区有 144 个是 reset/root break。
3. **当前 hard-root C2 无法给这些核心盲区定位高层相位。** retrospective C2 phase concentration 暂时不可检验，而不是已被否定。
4. **Causal C2 内部存在识别密度变化，但目前只算次级线索。** 不提升为状态信号。
5. **不在本轮修改 4/48，也不强行补波。** 先让高层 carrier 能跨 lower-level 边界连续表达，同时保留 reset/gap 元数据与因果确认时钟。

因此下一研究门是 #315 `scale-specific continuity bridge for coarse graphical hierarchy`。它的目的不是为了提高收益，而是先回答：低层 detector reset 是否真的必须物理切断更高层市场结构？候选 bridge 若能在不偷看未来的前提下恢复高层连续性并通过完整 OHLC 视觉验收，再把这 146 个盲区重新投影到连续 C2，届时才真正检验“底部横盘、顶部整理、趋势中段等位置是否更容易失明”。

## 关于 1 分钟数据

用户的澄清正式保留：1m 可以用于定义一个**新的更快 base scale**（例如 10×1m），这会真的增加一个层级和更多波，而不是只做 5m T0 的细采样。这个方向是合理的。

但当前这 5m 研究已经证明存在结构性 root fragmentation。若现在直接引入 1m，很可能只是在新的 base 上复制同样的层级断裂。因此先解决 #315，再单独预注册 1m-fast-base 实验；两件事不混在一起。

所有 signal / detector-repair / router / trade / production authority 继续为 false。
