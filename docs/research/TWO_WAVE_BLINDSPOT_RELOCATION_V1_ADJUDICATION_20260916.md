# Two-Wave Blindspot Relocation V1 裁决（2026-09-16）

## 结论

正式 run `35104182684-1` 已成功完成标准 `workflow_dispatch`、固定输入准备、断网/无凭据 compute、独立 verifier、cleanup 和私库回存。公共 source SHA 为 `68553cc3e9df578d274dc295e474c5abb47548f4`。本轮不训练、不看收益、不改 base 4/48，也不准入 1m。

旧 5m recognizer 共留下 146 个 blind episodes、11646 blind bars，其中 **144 个是 RESET_ROOT_BREAK，贡献 11610 bars，占全部 blind bars 的 99.6909%**。这 144 段里没有 Q1 小振幅 episode：Q4=126、Q3=14、Q2=4。因此此前“剩余盲区主要是因为没有振幅”明显不成立；当前主要缺陷仍是结构性断裂。

## continuity 后，144 段终于可以放回高层结构

C2：144 个 RESET_ROOT_BREAK 中，143 个与完整 C2 有重叠且 143 个多数区间可定位；overlap 中位数 100%，q10 仍有约 60.8%。

C3：142/144 有重叠且 142 个多数区间可定位；overlap 中位数 100%，q10 约 91.1%。

因此上一轮“盲区在 C2 本身也消失”的问题已经解决。高层 continuity 不是仅提高 C3 个数，而是真的让原来的失明段重新获得大周期坐标。

## 物理位置：retrospective map

单看完整事后结构，最强信号不是某个固定的“底部横盘”，而是**高层结构跨越较多低层 root/reset 边界**：

- C2 `crossing=2PLUS` 的 blind lift = **1.906x**；`crossing=1` 约 1.068x；`crossing=0` 为 0。
- C3 `crossing=2PLUS` 的 blind lift = **1.177x**；`crossing=1` 约 0.346x；`crossing=0` 为 0。
- C2 descriptor 中 RANGE 最富集，约 **1.144x**；DOWN 1.029x；UP 0.934x。
- C3 descriptor 本身几乎中性；但 C3 DOWN leg 约 **1.093x**，C3 Q4 amplitude 约 **1.174x**。
- joint descriptor 最富集的是 `C2 RANGE × C3 UP`（1.256x）、`C2 RANGE × C3 DOWN`（1.197x）、`C2 DOWN × C3 DOWN`（1.193x）。
- joint phase 最富集的是 `C2 LATE × C3 LATE`（1.234x），其次 `EARLY × EARLY`（1.145x）。

这些是 retrospective morphology，不能直接用作实时修复条件。

## 实时位置：causal as-of map

真正可用于下一轮 recognizer 候选设计的只有 causal-as-of：

### C2

- as-of 可解析率：全市场 98.94%，blind bars 99.36%。
- `crossing=2PLUS`：lift **1.220x**；`1`=0.959x；`0`=0.928x。
- `phase=LATE`：lift **1.091x**；MIDDLE≈0.990x；EARLY=0.639x。
- descriptor DOWN=1.060x，UP≈1.003x，RANGE=0.804x。

高支持 cell 中：

- `DOWN / leg UP / LATE / 2PLUS`：2488 bars，833 blind bars，lift **2.016x**。
- `UP / leg UP / MIDDLE / 2PLUS`：1897 / 512，lift **1.625x**。
- `DOWN / leg DOWN / LATE / 2PLUS`：1434 / 381，lift **1.600x**。

### C3

- as-of 可解析率：全市场 90.38%，blind bars 87.84%。
- descriptor DOWN：lift **1.179x**；UP=0.820x；RANGE=0.699x。
- `phase=MIDDLE`：lift **1.167x**；LATE=0.899x；EARLY=0.798x。
- `crossing=1`：1.096x；`2PLUS`≈1.006x；`0`=0.413x。

高支持 cell 中：

- `DOWN / leg UP / MIDDLE / 2PLUS`：3236 bars，989 blind bars，lift **1.840x**。
- `DOWN / leg UP / MIDDLE / 1`：1344 / 391，lift **1.751x**。
- `DOWN / leg DOWN / MIDDLE / 1`：2401 / 612，lift **1.535x**。

## 科学解释

1. **“底部横盘导致失明”没有得到单一规则支持。** RANGE 只在 retrospective C2 descriptor 上略富集；causal C2 RANGE 反而低于基线。
2. **真正稳定的结构变量是 continuity / crossing history。** 原识别器的 reset-root 断裂并不是随机发生，而是集中在已经跨过低层结构边界的更高层波里。
3. **实时相位也有结构：C2 late、C3 DOWN+middle 更危险。** 这说明本频段失明更像“大周期结构继续运行时，当前 4/48 kernel 因最大未完成腿/根边界语义把显著振幅切断”，而不是纯低振幅噪声。
4. 当前结果只允许设计下一轮候选 family，不允许直接把某个 cell 写成新 detector 规则；否则会把本轮结果当训练标签回填。

## 对 1m readiness 的影响

#321 仍未通过。当前 blind fraction 仍是 16.61%，而且 144 个 RESET_ROOT_BREAK 中 Q4=126、Q3=14、Q2=4、Q1=0。没有任何依据现在上传 1m。

下一步应先预注册少量、机制明确的 5m repair candidates，只使用 causal-as-of 信息，并用 #321 的原门槛和 anti-oversegmentation 约束做一次新的正式验证。失败就保留失败，不在本轮结果上继续调参。
