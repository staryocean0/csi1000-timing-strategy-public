# Two-Wave 策略历史沿革与研究架构总记忆

日期：2026-09-20

状态：`CANONICAL_PUBLIC_HISTORY_NARRATIVE`

用途：本文件记录 Two-Wave / 中证1000择时研究为什么从一个框架演化到下一个框架、每次转向解决了什么问题、又暴露了什么新问题。它的首要目标不是总结“最新结论”，而是防止后续开发因记忆丢失而重复旧路线、把历史失败重新包装成新假说，或陷入跨频段未来预测的递归套娃。

治理边界：本公库是 reviewed control plane。本文件作为公库 canonical historical narrative；项目 current authority 仍以私库 `CHAT_START.md`、`CLOUD_CURRENT.json` 及其冻结引用为准。若本文件需要成为私库权威历史记录，应通过受控 public→private governance sync 进入私库，禁止 Chat 直接修改私库。

---

## 0. 一句话总览

Two-Wave 的研究不是从“多频段模型”开始的。

它经历了三次框架升级：

1. **第一代：同级两波 → 第三波 continuation。**
   看到两个同级波后，假设第三段还会延续；问题是 continuation 并不稳定。
2. **第二代：跨频段条件化。**
   为解释“为什么有时持续、有时不持续”，引入 C1/C2 等相邻与更慢频段背景；问题是如果为了理解 T0 必须先预测 C1，而为了预测 C1 又预测 C2，会形成无穷递归。
3. **第三代候选：目标频段自身的 direction × survival / exhaustion。**
   不再要求先预测另一个频段的未来，而直接判断“当前目标频段是否仍有方向、该方向是否仍健康、是否正在进入 compression/exhaustion、当前状态是否接近退出”。

第三代目前是**候选研究架构，不是已完成的交易系统**。现有 compression 证据证明了因果 turn-risk / fast-loss hazard 信息，但还没有证明它单独足以形成经济上完备的买卖规则。

---

## 1. 第一代：Two-Wave continuation

### 1.1 原始思想

最早的策略对象非常简单：

> 在同一级别识别出两个波以后，用前两个波的结构判断第三个波是否仍会沿当前方向持续。

其交易直觉是典型的趋势延续：

- 已经形成方向；
- 两个同级波提供结构确认；
- 第三个波被视为 continuation opportunity；
- 一旦结构满足，就进入本频段交易。

这个阶段的优势是：

- 交易逻辑局部；
- 不依赖上一级或下一级未来预测；
- 容易解释；
- 本质上是趋势跟踪。

### 1.2 第一代暴露的问题

实际研究很快暴露出核心缺陷：

> **“已经有两个波”并不等于第三个波必然持续。**

有些 continuation 很顺；
有些很快失败；
有些反复翻转；
有些本频段看起来仍有方向，但更低频或更慢背景已经使该方向失去经济价值。

因此研究问题从：

> “两个波以后要不要做第三波？”

升级为：

> **“什么环境下第三波会持续，什么环境下不会持续？”**

这是第一次框架级转向的原因。

---

## 2. 第二代：跨频段条件化

### 2.1 为什么开始研究 C1 / C2

为了回答 continuation 为什么不稳定，研究开始引入多尺度图形分解。

采用递归骨架/残差表示：

- `X0`：原始价格；
- `S0`：本级别已确认波形成的骨架；
- `C1 = S0 - S1`：紧邻本级别的一级低频成分；
- `C2 = S1 - S2`：更慢一级低频成分；
- 后续可继续递归。

该阶段形成的核心金融命题是：

> 本级别 T0 的 continuation 可能同时受到紧邻低频 C1 和更慢背景 C2 的条件影响。

其中：

- C1 距离 T0 最近，对 T0 的反复、快亏、局部稳定性尤其重要；
- C2 更适合承担较慢背景与趋势延续环境；
- 相邻频段不应被简单理解成“上级预测下级”，而是不同尺度的条件状态。

### 2.2 第二代取得的真正进步

这一阶段的重要进步不是“找到了万能跨频段规则”，而是确认：

1. **T0 不能仅由 T0 的静态形态解释。**
2. **C1 对 T0 的局部执行风险有重要影响，不能忽略。**
3. **C2/C3 等更慢频段更适合被理解为背景状态，而不是机械监督者。**
4. **频段的实际尺度比必须从识别出的波测量，不能预设固定 2–3 倍。**
5. **T0/C1 更合理地被视为不同 execution rhythm，而不是固定 supervisor/follower。**

随后 C2/C3 主线进一步改造成：

> 显式 C2/C3 bandpass / residual trend state → 选择 E0=T0 或 E1=T1/C1 的执行节奏。

截至本文件日期，这条线仍处于 causal observability / representation qualification 阶段，尚未形成生产 router。

### 2.3 第二代同时埋下了一个结构性风险：递归套娃

一旦研究逻辑变成：

> 为了知道 T0 能不能继续，先知道 C1 接下来会怎样；

就自然会出现下一问：

> 为了知道 C1 接下来会怎样，是不是又要知道 C2？

继而：

> 为了知道 C2，是不是又要预测 C3？

形成：

[
T0 leftarrow future(C1) leftarrow future(C2) leftarrow future(C3) leftarrow cdots
]

这不是一个可闭合的策略架构。

因为每一个“解释变量”本身又成为新的未来预测目标。

**这条递归未来预测链从 2026-09-20 起被明确列为禁止架构。**

---

## 3. 为什么 C1 研究把我们带到了第三代候选架构

### 3.1 原始问题仍然来自第二代

C1 的研究并不是为了发明单频段策略。

最初问题是：

> C1 对 T0 影响很大，但 C1 又不能直接跟随；能否提前知道 C1 什么时候要失稳，从而减少它对 T0 的负面影响？

为了回答这个问题，研究进入 C1 turn precursor。

### 3.2 从“terminal thrust”转向 compression / exhaustion

早期 event-only 观察一度提示 turn 前可能出现 terminal thrust。

但 matched non-turn controls 否定了这个解释。

真正稳定留下来的前兆是：

- 8-bar absolute move 更小；
- 8-bar range 更窄；
- realized volatility 更低；
- path efficiency 更低；
- old-direction progress 更弱。

也就是说：

> **即将发生 C1 turn 的地方，不是先出现更强的旧方向冲刺，而是经常先出现 compression / exhaustion。**

#485 的 matched-control specificity 和 #493 的 evidence-age rematching 都保留了这一结构。

### 3.3 #507 把描述性前兆变成 causal turn-risk ranking

#507 没有使用 T0 PnL 拟合，也没有训练 turn classifier。

它在实际 T0 signal bar 上，仅使用当时可知的：

- `abs_ret_8`
- `range_8`
- `rv_8`
- `efficiency_8`

采用 prior-year walk-forward percentile，并等权形成 causal compression score。

authoritative #507 v2 结果：

- scored T0 signals：945；
- B1 future C1-turn rate：约 14.79%；
- B5 future C1-turn rate：约 24.86%；
- B5-B1：约 +10.07 percentage points；
- B5/B1 risk ratio：约 1.68；
- bootstrap 支持风险排序；
- verdict：`C1_COMPRESSION_RISK_RANKING_SUPPORTED`。

因此当时真正得到的不是“转折预测器”，而是：

> **compression/exhaustion 能因果地提高当前 C1 状态在短窗口内退出/转折的风险排序。**

---

## 4. compression 之后的一系列研究：明确它能做什么、不能做什么

### 4.1 #537 / #582：统计风险有效，不等于直接交易 veto 有效

将冻结的 #507 score 接到 T0 own-lifecycle outcome 后：

B1..B5 fast-loss rate：

- B1：30.28%
- B2：32.57%
- B3：42.36%
- B4：43.02%
- B5：49.72%

fast-loss rank monotonicity 很强。

但 mean-return degradation 不稳定：

- B5-B1 mean net ≈ -7.22bp；
- 95% CI 跨零；
- B5 自身 mean net 仍为正。

因此：

> compression 更像 **execution fragility / whipsaw hazard**，不是“高 compression 就不做”的 hard veto。

这是一个非常重要的项目级区分：

**因子有效性 ≠ 交易规则完备性。**

### 4.2 #587：风险集中在趋势生命周期早期

path/hazard atlas 进一步发现：

B5 相比 B1 的 losing-exit hazard 在最初 8–21 bars 已明显抬升。

同时，熬过早期危险窗口的高 compression trades 仍可能保有很强的正向 path value。

因此机制更接近：

> 高 compression 增加 early failure mass，但没有消灭 survivor right tail。

这解释了为什么：

- fast-loss 很显著；
- final mean return 却不一定显著变坏。

### 4.3 #540：统一 defer-8 失败

既然 early failure 集中在前 8 bars，一个自然想法是高 compression 全部延迟 8 bars。

结果：

- 确实跳过了一批几乎纯 fast-loss 的坏交易；
- 但也显著损伤了 surviving winners 的收益；
- 总体 policy delta 不支持。

因此：

> **识别 hazard 成功，并不自动意味着机械延迟就是正确干预。**

### 4.4 turn direction 研究没有成功升级

后续 signed-ret8 / harmful-vs-helpful turn 研究表明：

- compression 能告诉我们“更容易发生 transition”；
- 但不能可靠告诉我们 transition 对 T0 是 harmful 还是 helpful；
- 也不能稳定预测未来 turn direction。

所以 compression 当前仍应被定义为：

> **transition / state-exit risk information，而不是 direction information。**

### 4.5 #561：高 compression 会让 T0-side 作为 C1 direction proxy 变脆

T0 side 对 retrospective C1 current direction 有一定默认信息，但 B1→B5 fidelity 明显下降。

这进一步支持：

> compression 不是新方向本身，而是“当前方向/状态可信度正在下降”的 warning。

但五档完整 calibrated confidence curve 没有通过预注册门，因此不能把它升级成完整 state-confidence model。

### 4.6 #615：静态 C1 relation × compression interaction 最终没有通过

#615 直接检验：

- causal C1 与 T0 ALIGNED 时，高 compression 是否伤害 T0；
- causal C1 与 T0 OPPOSED 时，高 compression 是否反而帮助 T0；
- DID 是否稳定为正。

点估计方向部分符合直觉，但三个核心 bootstrap CI gate 全部失败。

最终受控 verdict：

`T0_CAUSAL_C1_COMPRESSION_INTERACTION_NOT_SUPPORTED`

#615 已经：

- 通过 standard workflow_dispatch；
- independent verifier PASS；
- private receipt / Release 回读验签；
- exact result 与本地复现逐字节一致；
- 正式关闭。

因此：

> 当前 causal C1 ALIGNED/OPPOSED × compression 不授权静态 router、veto 或 override。

---

## 5. 第三代候选架构：direction × survival，而不是“预测另一个频段的未来”

### 5.1 新问题不是“下一步往哪转”

第三代不把目标定义成：

> UP 之后是否一定变 DOWN？

而是定义成：

> **当前 UP 是否正在接近结束？**

同理：

> 当前 DOWN 是否正在接近结束？

这把问题从 next-state classification 改成 current-state survival / exit hazard。

### 5.2 一个频段至少有两个正交维度

以后更合理的状态表达不是只有：

- UP
- RANGE
- DOWN

而是至少拆成：

**Direction**
- UP
- DOWN
- 或当前无明确方向

以及：

**State quality / survival**
- HEALTHY
- WEAKENING
- EXHAUSTING
- HIGH_EXIT_RISK

于是可能出现：

- UP_HEALTHY
- UP_EXHAUSTING
- DOWN_HEALTHY
- DOWN_EXHAUSTING

compression 不是第四个方向。

它更接近：

> **当前 directional state 的稳定性 / 生存率正在下降。**

### 5.3 RANGE 的角色也需要重新理解

RANGE 不一定是与 UP / DOWN 完全对称的永久第三类。

其中一部分可能只是：

> 一个 directional state 离开旧状态、尚未进入新稳定方向时的 transition region。

因此后续研究应允许：

[
UP ightarrow EXHAUSTION ightarrow RANGE ightarrow DOWN
]

也允许：

[
UP ightarrow EXHAUSTION ightarrow RANGE ightarrow UP_RENEWED
]

第三代的目标不是预判最后落在哪边，而是提前识别：

> **旧的 UP 已经不再值得继续信任。**

---

## 6. 目前还没有闭合的关键缺口

第三代不能因为 #507 成功就被视为已完成。

### 6.1 缺口一：因子有效性是否足够转化成交易有效性

B1≈15% 与 B5≈25% 的 future-turn risk 差异足以证明信息含量。

但 B5 仍有约 75% 没有在冻结窗口内发生该类 turn。

因此不能简单写成：

> B5 → exit。

真正需要验证的是：

> **当目标频段自身进入 exhaustion / low-efficiency / high-exit-risk 时，“继续持有”相对于“退出”的条件经济价值是否稳定下降到值得改变持仓。**

这是 trading completeness gate。

### 6.2 缺口二：当前 #507 target 是 C1 slope-sign turn，不完全等于“当前趋势状态结束”

如果当前 UP：

- UP→DOWN 显然是 state exit；
- UP→RANGE 同样应该算旧 UP 结束；
- 但 slope-sign turn target 未必完整覆盖 UP→RANGE。

因此下一门不是继续猜 turn direction，而是重新冻结更符合策略目标的 target：

> **current directional state exit**

即：

- 当前 UP 只要离开 UP，即计为 exit；
- 当前 DOWN 只要离开 DOWN，即计为 exit；
- 不要求事先知道下一状态是 RANGE 还是反向趋势。

### 6.3 缺口三：单频段是否足够

现有证据不能证明跨频段信息已经无用。

第三代必须和第二代做公平增量比较，而不是用理论直觉直接取代第二代。

---

## 7. 从现在开始的“不套娃”架构原则

### 7.1 唯一预测目标

对于目标频段 `Sk`，只预测：

[
P(	ext{current } S_k 	ext{ directional state exits within horizon } H mid I_t)
]

即：

> **目标频段当前趋势状态还能不能继续。**

### 7.2 第一层输入：目标频段自身信息

允许：

- current direction；
- slope / pace；
- amplitude；
- path efficiency；
- range；
- realized volatility；
- compression；
- contraction dynamics；
- state age；
- causal evidence age；
- 其他在当前决策时钟真实可知的本频段状态量。

这是 **Local-only** 模型。

### 7.3 第二层输入：其他频段只能提供“当前已知 context”

如果 Local-only 不够，可以加入：

- current causal C1 state；
- current causal C2 state；
- current LP/BP relation；
- 当前可观察的相对方向、强弱、年龄、相位证据。

但禁止先预测它们的未来。

允许：

[
P(T0 exit mid T0 local, current C1, current C2)
]

禁止：

[
future(C2)ightarrow future(C1)ightarrow future(T0)
]

### 7.4 明确禁止的递归未来预测模式

从本文件起，以下架构默认不接受，除非未来有单独项目级重新授权：

1. 为预测 T0，先建立 C1 future predictor；
2. 为预测 C1，再建立 C2 future predictor；
3. 为预测 C2，再递归建立 C3 future predictor；
4. 把某一级 future forecast 当作下一级必需输入；
5. 用“还需要预测上一层”作为无限延伸研究链的理由。

原因不是“跨频段没有信息”，而是：

> **这种结构没有天然闭合边界，会把每一个输入变成新的预测任务。**

---

## 8. 后续公平比较应固定成三层模型，而不是三层套娃

针对同一个目标频段、同一个 state-exit target、同一个 knowledge clock：

### Model A — Local-only

只用目标频段自身信息。

回答：

> **一个频段是否已经包含足够信息判断自己的趋势是否正在失稳？**

### Model B — Local + nearest current context

在 A 的基础上只加入紧邻频段当前已知 causal state。

回答：

> C1 当前状态对 T0 state survival 是否提供真实增量？

不预测 C1 future。

### Model C — Local + nearest + slower current context

再加入更慢频段当前状态。

回答：

> C2 当前背景是否在 A/B 之外继续提供稳定增量？

不预测 C2 future。

三者必须：

- 同一个 target；
- 同一个样本；
- 同一个 horizon；
- 同一个信息时钟；
- 同样的 OOS / walk-forward 规则；
- 同样的复杂度约束；
- 不允许因为看到 outcome 后再改变 state 定义或 horizon。

这才是第二代与第三代路径的公平比较。

---

## 9. 当前项目应如何重新解释以前的工作

### 9.1 第一代没有失败到“应被删除”

Two-Wave continuation 仍是交易行为的起点。

它告诉我们：

> **趋势可以存在，但 continuation 不是无条件的。**

### 9.2 第二代也没有因为第三代出现而作废

跨频段研究已经证明：

> 当前上下文确实可能影响目标频段的 continuation / fragility。

它应被降级成：

> **incremental current context**

而不是：

> **必须先预测的 supervisor future。**

### 9.3 第三代目前不是“单频段已经解决一切”

第三代目前只提出一个更可闭合的研究对象：

> **目标频段自身的 direction × state survival。**

它是否能单独达到可交易门槛，尚待验证。

如果 Local-only 不够：

> 回到跨频段 context 增量。

但不能回到递归预测链。

---

## 10. 已经明确不要重复的路线

以下历史问题已经有足够证据，不应因记忆丢失重新包装：

- 两个同级波出现后默认第三波必然 continuation；
- 把 C1/T1 当作天然 supervisor、T0 当 follower；
- 把固定层号直接等价成固定周期比；
- 把 retrospective C2 phase 当成实时可得状态；
- 单用 base/current-band slope 推 C2 semantic phase；
- high compression 直接 hard-veto T0；
- high compression 全体统一 defer-8；
- 用 signed ret8 作为稳定 C1 turn-direction predictor；
- 把 compression 当成 direction predictor；
- 用 static causal C1 ALIGNED/OPPOSED × compression 直接做 router；
- outcome 之后移动 B1..B5 边界或合并 cells 去救负结果；
- 为解释一个频段而无限预测更高一级频段的 future state。

这些失败和边界是资产，不是需要清理的噪音。

---

## 11. 当前两条研究线如何共存

截至 2026-09-20，Two-Wave 实际上有两条不同问题线：

### A. C2/C3 routing thread

研究：

> 更慢的 causal state 是否能决定使用 E0=T0 还是 E1=T1/C1 execution rhythm？

当前仍需完成 causal observability、公平 execution contract 和增量验证。

### B. target-frequency survival / exhaustion thread

研究：

> 目标频段当前 directional state 是否可以仅凭自身 causal path quality 提前识别 state exit hazard？

这条线源于 C1 compression 研究，但目标已经高于最初的 “C1 如何影响 T0”。

两条线不应互相覆盖：

- A 研究 execution rhythm context；
- B 研究 target state survival。

未来如果 B 的 Local-only 已经足够，A 的经济增量可能下降；
如果 B 不足，A 可作为 current-context incremental layer。

结果必须由公平对比决定，不能预设。

---

## 12. 下一开发门：Single-frequency state-exit hazard

下一步不再研究：

> “转折以后往哪边？”

而冻结：

> **“当前 directional state 是否会在未来 H 内结束？”**

第一轮优先在已有 C1 compression evidence 上做定义闭合，因为：

- 已有 matched precursor evidence；
- 已有 causal compression score；
- 已有 prefix replay；
- 已有严格 frozen input identity；
- 已有大量负面 economic/intervention evidence 可防止事后救援。

第一轮必须先回答：

1. 如何定义 causal current UP / DOWN；
2. 如何定义离开当前状态，包括进入 RANGE；
3. horizon 是否按本频段自身尺度归一化，而不是任意固定 bars；
4. Local-only features 必须 outcome-blind 冻结；
5. primary target 是 state exit，不是 next direction；
6. 只有 Local-only 完成后，才能测试 current C1/C2 context incremental value；
7. 不允许把任何 other-frequency future prediction 当输入。

---

## 13. 当前研究原则

从本文件开始，后续开发默认遵守：

### Principle 1 — Target-first

每个研究先明确目标频段和唯一 outcome。

### Principle 2 — Current information only

输入必须在 decision clock 已知。

### Principle 3 — Local before context

先测目标频段自身信息，再测其他频段 current context 的增量。

### Principle 4 — No recursive future dependency

其他频段 future forecast 不能成为目标频段预测的必需中间变量。

### Principle 5 — Statistical value is not trading value

hazard lift、AUC、risk ratio 只证明信息，不自动授权 entry/exit。

### Principle 6 — Intervention requires separate economic gate

只有预测层冻结后，才能比较 hold / exit / scale / route 等干预。

### Principle 7 — Preserve negative evidence

负结果不删、不调参救援、不改写历史。

---

## 14. 本文件的维护规则

这份历史沿革文档不是一次性总结。

未来每次出现**框架级转向**时，必须追加：

1. 上一框架当时解决什么问题；
2. 新证据暴露了什么结构性不足；
3. 为什么不能只局部修补；
4. 新框架改变了哪些研究对象或依赖关系；
5. 哪些历史结论继续有效；
6. 哪些结论被降级或明确否证；
7. 新框架新增了什么禁止事项；
8. 对应 issue / prereg / result / controlled receipt 的固定引用。

不得只写“最新正确答案”而删除演化过程。

---

## 15. 关键历史证据索引

框架与表示：

- `TWO_WAVE_MULTISCALE_GEOMETRIC_DECOMPOSITION_REFRAME_20260916.md`
- `TWO_WAVE_C2_C3_BANDPASS_ROUTING_THREAD_AUTHORITY_20260919.md`
- `TWO_WAVE_C2_C3_BANDPASS_ROUTING_ROADMAP_20260919.md`
- `TWO_WAVE_R2B_LP_BP_DUAL_TRACK_CHARTER_20260919.md`

C1 compression / exhaustion：

- `TWO_WAVE_C1_LEAD8_PRECURSOR_RESULT_20260919.md`
- `TWO_WAVE_C1_LEAD8_SPECIFICITY_RESULT_20260919.md`
- `TWO_WAVE_C1_LEAD8_COMPRESSION_REMATCH_RESULT_20260919.md`
- `TWO_WAVE_C1_COMPRESSION_RISK_RANKING_RESULT_20260919.md`

经济含义与 path hazard：

- `TWO_WAVE_T0_OUTCOME_BY_C1_COMPRESSION_RESULT_20260919.md`
- `TWO_WAVE_T0_C1_COMPRESSION_UTILITY_RESULT_20260919.md`
- `TWO_WAVE_T0_COMPRESSION_PATH_HAZARD_RESULT_20260919.md`
- `TWO_WAVE_T0_DEFER8_HIGH_COMPRESSION_RESULT_20260919.md`

方向与交互负结果：

- `TWO_WAVE_C1_HARMFUL_HELPFUL_TURN_RESULT_20260919.md`
- `TWO_WAVE_C1_SIGNED_TURN_DIRECTION_RESULT_20260919.md`
- `TWO_WAVE_T0_SIDE_C1_FRAGILITY_RESULT_20260919.md`
- `TWO_WAVE_T0_CAUSAL_C1_COMPRESSION_INTERACTION_RESULT_20260920.md`
- `TWO_WAVE_T0_CAUSAL_C1_COMPRESSION_INTERACTION_EXECUTION_ACCEPTANCE_20260920.md`

当前 compression side-thread authority：

- `TWO_WAVE_T0_C1_CAUSAL_COMPRESSION_THREAD_AUTHORITY_20260920.md`

---

## 16. 当前项目级判断

当前不应宣布：

> “跨频段关系已经不需要。”

也不应宣布：

> “单频段 compression 已经足够交易。”

当前真正成立的是：

> **我们已经找到一个更容易闭合、不会递归套娃的统一研究目标：目标频段当前 directional state 的 survival / exit hazard。**

后续研究先让 Local-only 自证。

只有当 Local-only 不能达到预先冻结的信息门与经济门时，才逐层加入其他频段**当前已知状态**，测量真实增量。

这样，无论最终是单频段胜出还是跨频段 context 必须保留，整个策略架构都能在有限层级内闭合，而不会重新进入 `T0 ← future(C1) ← future(C2) ← ...` 的循环依赖。

---

## 17. 2026-09-20：第三代 Local-only 第一门完成，结论是“有信息，但不足以普适替代跨频段 context”

Issue #624 完成了本文件第 12 节定义的第一门：

> 只使用目标频段自身的 causal compression / exhaustion 信息，能否稳定判断当前 directional state 即将退出？

为避免 predictor-target 机械重叠，正式执行前 Amendment A 将 primary target 从五态 exact-label exit 修正为冻结 recognizer pre-veto direction carrier 的结构性退出：

- DIR_UP 离开 UP，进入 RANGE 或 DOWN，算 state exit；
- DIR_DOWN 离开 DOWN，进入 RANGE 或 UP，算 state exit；
- LOW_AMPLITUDE_VETO / FINER_SCALE_OUT_OF_BAND 只作为诊断，不参与 primary gate。

### 17.1 结果不是“单频段无效”

Local-only compression 的 pooled 信息非常明显：

- 2018–2020 scored directional rows：29,713；
- B1 EXIT_NEXT8：29.11%；
- B5 EXIT_NEXT8：40.52%；
- B5−B1：+11.40pp；
- 95% block-bootstrap CI：[+8.16pp,+14.49pp]；
- B5/B1：1.392x；
- band-rate Spearman：1.00；
- B5>B1：3/3 test years；
- positive B5−B1：8/8 overlap cohorts；
- age-standardized B5−B1：+8.65pp；
- +16 horizon B5−B1：+9.61pp。

因此可以保留一个重要结论：

> **目标频段自身确实包含关于“当前方向还能不能继续”的 causal survival / exit-hazard 信息。**

这验证了第三代架构不是空想。

### 17.2 但它没有通过“普适 Local-only 替代层”的硬门

冻结 universal gate 仍然失败，主要有两点：

1. pooled continuous-score ROC AUC = 0.5469，低于预注册 0.55；
2. CURRENT_UP 的 B5−B1 只有 +3.96pp，95% CI [-1.27pp,+9.45pp]，不能排除零。

方向不对称非常明显。

CURRENT_DOWN：

- B5−B1 = +17.16pp；
- 95% CI [+13.17pp,+21.44pp]；
- AUC = 0.5687；
- band-rate Spearman = 1.00。

CURRENT_UP：

- B5−B1 = +3.96pp；
- CI 跨零；
- AUC = 0.5255；
- band-rate Spearman = 0.60。

因此正式 verdict：

`LOCAL_COMPRESSION_STATE_EXIT_HAZARD_NOT_SUPPORTED`

这里的 NOT_SUPPORTED 指：

> **不支持“一套对 UP/DOWN 对称适用的 Local-only compression rule 足以替代跨频段 context”。**

它不表示 compression 没有信息。

### 17.3 这次结果解决了此前的第一层担忧

此前最大的疑问之一是：

> compression 从约 15% 到约 25% 的 turn-risk lift，究竟只是统计因子有效，还是可能成为更完整的 state-survival 信息？

#624 把研究对象改成更贴近策略目标的“本频段 directional state 是否退出”，结果 pooled separation 已经达到 +11.40pp，而且经过年龄、年份、overlap cohort 和 +16 horizon 后仍保留。

所以：

> **compression 不只是对 retrospective C1 turn 有统计关系，它确实承载了目标频段自身 state-survival 的信息。**

但这仍然只是 information layer，不是交易 exit rule。

“看到 B5 就平仓”仍未被授权。

### 17.4 这次结果也回答了第二层担忧：第三代没有完全跳过第二代

用户此前担忧：

> 如果 Local-only 真能完整解决 continuation，第二代跨频段研究就显得多余；但如果它解决不了，我们又会不会重新掉回 C1→C2→C3 的套娃？

#624 给出的答案正好处在中间：

- Local-only 有真实、较强的信息；
- 但它不能在 UP/DOWN 两侧都达到冻结普适门；
- 因此跨频段 context 仍有潜在增量价值；
- 但跨频段必须以 **current observable context** 的形式进入，而不能以 future predictor 链进入。

这意味着第二代不是被推翻，而是被重新定位：

> **从“必须预测的 supervisor future”降级为“对同一个 target 的 incremental current context”。**

### 17.5 下一门正式从 Model A 推进到 Model B

Model A：

[
P(exitmid local target frequency)
]

已经完成。

下一门只能研究：

[
P(exitmid local baseline, current nearest context)
]

要求：

1. primary target 与 #624 完全相同；
2. Local-only baseline 固定，不重新调；
3. other-frequency feature 必须在 decision clock 当时已知；
4. 不允许使用 future(C1)、future(C2)；
5. 首先测 incremental information，而不是直接设计交易规则；
6. 只有 incremental information 成立后，才允许单独预注册 economic intervention。

如果 Model B 没有稳定增量，则 nearest context 不保留。

如果 Model B 有增量，再决定是否有必要测试 Model C：

[
P(exitmid local, current nearest, current slower)
]

仍然不得形成 recursive future dependency。

### 17.6 #624 controlled acceptance 与可复现性

最终 canonical governed run：

- public run：`35488698309`
- identity：`35488698309-1`
- public source SHA：`828a64c763ba1e4f08b126a3766e54bb73a8e4d8`
- independent verifier：PASS
- verified rows：29,713
- verified blocks：38
- canonical ledger SHA256：
  `c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f`
- canonical exact-result SHA256：
  `0760393f9a27b4a7db2ad65a931e449c68ca71c2aeba7a657867d9929743519b`

前两次 governed runs 因跨运行环境浮点末位序列化不同而未作为 canonical byte receipt，但科学结果完全一致，均保留为历史证据。

相关文件：

- `TWO_WAVE_LOCAL_STATE_EXIT_COMPRESSION_PREREG_20260920.*`
- `TWO_WAVE_LOCAL_STATE_EXIT_COMPRESSION_PREREG_AMENDMENT_A_20260920.*`
- `TWO_WAVE_LOCAL_STATE_EXIT_COMPRESSION_RESULT_20260920.*`
- `TWO_WAVE_LOCAL_STATE_EXIT_COMPRESSION_REPRODUCIBILITY_REPAIR_20260920.md`
- `TWO_WAVE_LOCAL_STATE_EXIT_COMPRESSION_EXECUTION_ACCEPTANCE_20260920.*`

### 17.7 更新后的项目级判断

截至本次闭合，项目不再处于：

> “Local-only 是否值得试？”

而是进入：

> **“Local-only 已证明有信息，但未证明足够；现在只允许测 current cross-frequency context 的真实增量。”**

因此当前最重要的架构边界是：

[
	ext{Local baseline}
ightarrow
+	ext{ current context}
]

而不是：

[
T0
leftarrow future(C1)
leftarrow future(C2)
leftarrow future(C3)
]

这标志着项目已经找到一条可以继续研究、同时天然有终止边界的非套娃路径。

---

## 18. 第四代第一次 current-context 增量检验：P128 Model B 未获得支持

### 18.1 为什么必须做这一门

#624 同时证明了两件事：本频段 local compression 对 directional state-survival 有真实信息；但一套对 CURRENT_UP / CURRENT_DOWN 普适的 Local-only gate 未获得支持。

因此项目没有回到“预测 C1 再预测 C2”的旧递归结构，而是冻结了一个更小的问题：

> 在同一个 #624 STRUCTURAL_EXIT_NEXT8 目标上，已经控制当前方向、carrier age 和 frozen local compression score 后，一个当时可知的 nearest current context 是否还有额外概率信息？

Issue #635 只允许一个候选：P128 raw-price trailing OLS normalized phase，只看当前时点可知的 ALIGNED / NEUTRAL / OPPOSED；不使用 future(C1)，不使用 stage1 causal leg，不测试 P256，也不搜索新的窗口、carrier 或阈值。

这就是第四代第一次真正的 non-recursive Model B。

### 18.2 Model A / Model B 的冻结比较

Model A 在 #624 冻结对象上做固定概率校准：10 个 direction × age-cell intercepts + 2 个 direction-specific compression slopes，共 12 参数。

Model B 在完全相同 mature/common-support prior rows 上，只增加当前 P128 context 的 4 个固定 categorical terms，总计 16 参数。
两边使用同一 target、同一 29,713 行 2018–2020 evaluation universe、同一 prior-only annual fitting、同一 label-maturity rule、同一 ridge lambda=0.001、同一 Brier / log-loss paired evaluation、同一 20 trading-day block bootstrap（5000 reps，seed 20260920）。

### 18.3 受控结果：P128 没有提供稳定增量

第一份完整、独立 verifier PASS 的 governed result：

- public run：35500372173
- identity：35500372173-1
- public source SHA：42c86adb5de9632b51d11ac1ed1ec9a0c835457b
- verified evaluation rows：29,713
- baseline #624 row/hash identity：PASS
- complete causal prefix / future perturbation：PASS
- support gate：PASS
- independent verifier：PASS

冻结 verdict：MODEL_B_P128_STATE_EXIT_INCREMENT_NOT_SUPPORTED。

pooled proper-scoring result：

- Model A Brier = 0.216993686942
- Model B Brier = 0.217204110603
- Brier gain (A−B) = -0.000210423662
- relative Brier gain = -0.09697%
- Model A log-loss = 0.625007587553
- Model B log-loss = 0.625326059446
- log-loss gain (A−B) = -0.000318471893

也就是说，P128 context 并不是“有一点但不够显著”，而是在冻结 proper-scoring comparison 下 pooled 方向本身就是轻微变差。

AUC 虽然从 0.61119 小幅升到 0.61369，但本门预注册的核心不是 ranking-only AUC，而是概率预测增量；Brier 与 log-loss 都没有改善。

### 18.4 稳定性门为什么没有通过

pooled 20-day block bootstrap：

- Brier gain 95% CI = [-0.00080168, +0.00037942]
- log-loss gain 95% CI = [-0.00163513, +0.00099600]

两侧方向均没有正的 CI。

CURRENT_UP：relative Brier gain = -0.01509%，Brier gain CI low = -0.00068144。

CURRENT_DOWN：relative Brier gain = -0.17549%，Brier gain CI low = -0.00147275。

年度也不稳定：2018 Brier gain = -0.00000532；2019 = +0.00016040；2020 = -0.00077164。
冻结 gate 中只有 support_and_causal=true、ECE 增量门=true；其余核心 incremental-information gates 均未通过，包括 1% relative Brier minimum、pooled 两个 CI、UP/DOWN 两侧 CI、三年全正、8 cohorts 中至少 6 个为正、common-support Brier gain > 0。

### 18.5 这次负结果真正排除了什么

这次结果排除的是一个非常具体的假设：

> #429 中曾经具有 marginal persistence conditioning 信息的 P128 raw-price current phase，在控制方向、年龄和 #624 frozen local compression score 后，并没有提供稳定的 conditional incremental probability information。

这不否定 #429 的 marginal finding。两者回答的问题不同：#429 问 P128 单独作为 parent phase 是否与 post-delay persistence 有关系；#635 问已经知道 local state/compression/age 后，P128 是否还有增量。

答案现在是：marginal 曾获得支持；conditional incremental 本门不支持。

### 18.6 递归套娃在这里获得了真实终止边界

#635 预注册明确规定：negative / insufficient result closes this candidate；不得自动升级到更慢 context。

因此当前不允许因为 P128 失败就自然变成 P128 -> P256 -> C2 -> C3 -> ...，也不允许解释为“nearest context 不行，所以继续找 slower context 总会找到一个”。

正确的项目级结论是：当前这个 nearest current-context 候选应被删除。
下一步如果要研究任何新的跨频段 context，必须重新提出一个独立、可证伪的新假设，并重新说明为什么它不是 P128 的事后替代、为什么有独立机制依据、为什么不会重新形成 recursive future dependency，以及什么负结果会终止该新候选。

### 18.7 当前架构状态

经过 #624 和 #635，当前证据链变成：

1. Local compression 对本频段 state survival 确实有信息；
2. Local-only universal gate 未获得支持；
3. nearest P128 current context 的 conditional incremental value 也未获得支持；
4. 因此不能把 P128 保留为默认 supervisor；
5. 也不能自动升级 slower context。

这使项目进一步收缩为：Local state-survival baseline 是当前仍被证据保留的主体；任何新的 context 必须重新获得独立增量资格。

本门仍然只是 information-layer 研究，没有获得 economic intervention、signal、router、trade、paper、live 或 production authority。

### 18.8 governed execution 的工程历史

首次 attempt 35499292209-1 在 scientific output 写出前被 host watchdog 截断：profile 内部原允许 producer/verifier 各 2400 秒，但 shared host watchdog 仍为 660 / 210 秒。该运行没有 exact JSON / scored ledger，因此是工程失败，不是科学负结果；其 failure receipt / Release 永久保留。
随后 #635 专用 broker 将 producer timeout 固定为 900 秒、verifier timeout 固定为 900 秒、host watchdog 固定为 960 秒；shared broker 与其他 profile 不变。

在该修复后，35500372173-1 首次形成完整 scientific result 并由独立 verifier PASS。

其 private Release：

- release id：392374589
- archive SHA256：9d0b61bd9150d13a75c600dcfb24c5cc781a7966d70c2f85463a04ff52d85dbf
- exact result SHA256：4ef2a23577ef782c5622df1906dde794c11656614dbf0735855db30f213d5531
- scored ledger SHA256：eb9d1efca3e8327e5f8ba08b9e7d546c67da76d5e80595b6f314782a3863bbd1

该 run 的 receipt 将 new_training 错记为 false；这是 generic publisher 的元数据缺陷，不影响 Release 中 scientific result bytes。#641 只修正该 receipt 元数据路径，不改变任何科学对象或结果门。

最终 canonical replay：

- public run：35500929714
- identity：35500929714-1
- public source SHA：3ada17b8cad87b98574866400bc7cbed404072a8
- private receipt：passed / archive_uploaded_and_verified
- receipt new_training：true
- private Release id：392382447
- archive SHA256：db7bd62c2720f9619bf879a4320e23808eb15709cb88000ce2cfc733957c4fc1
- exact result SHA256：4ef2a23577ef782c5622df1906dde794c11656614dbf0735855db30f213d5531
- scored ledger SHA256：eb9d1efca3e8327e5f8ba08b9e7d546c67da76d5e80595b6f314782a3863bbd1
- independent verifier：PASS，29,713 rows / 38 blocks

canonical replay 的 exact result 与 scored ledger 和第一完整 run 逐字节一致，因此 #635 的科学 verdict 可正式接受为受控、可复现的 NOT_SUPPORTED 结果。

### 18.9 与项目级 current authority 的边界

本节记录的是已经通过本双仓控制面执行、由私库 run receipt / Release 接受的 Two-Wave #635 研究结果。

它不会因为写入公库历史文档就自动替换项目级 current authority。按照仓库治理，项目 current authority 仍由私库根 CHAT_START.md、CLOUD_CURRENT.json 及其引用合同定义；当前它们仍指向 Risk Tool 2.0 Phase-1。

因此本次闭合只接受 #635 的研究证据与历史沿革，不直接修改私库根控制文件，也不把 Two-Wave 宣称成新的 current research anchor。

---

## 19. 2026-09-20：#647 direction asymmetry 机制审计闭合为 MIXED_OR_INCONCLUSIVE

### 19.1 为什么回到本地机制，而不是继续升级 context

#624 留下的核心未解问题不是“再找一个更慢频段”，而是同一套 frozen Local-only compression 为什么在 CURRENT_DOWN 强、在 CURRENT_UP 弱。#635 又已经否定 P128 作为第一个 non-recursive current-context 增量候选，因此 #647 按冻结边界只审计 #624 已接受 ledger 内四个本地 component 与 carrier age，不读取任何 P128/P256/C1/C2/C3，也不引入 future-state predictor、PnL、routing 或新 feature family。

唯一输入仍是 #624 canonical scored ledger：

- accepted #624 governed identity / ledger identity：35488698309-1；
- rows：29,713；years：2018/2019/2020；
- ledger SHA256：c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f；
- target：STRUCTURAL_EXIT_NEXT8；
- components：risk_abs_ret_8 / risk_range_8 / risk_rv_8 / risk_efficiency_8；
- reference：frozen equal-weight compression_score；
- bootstrap：20 trading-day blocks，5000 reps，seed 20260920。

### 19.2 governed execution 与 block-phase 修复

第一次正式 run 35511741696-1 在 compute 阶段失败。失败不是科学负结果：#647 初版从 2018 ledger 首日重新编号 20-day blocks，因此 730 个 ledger trading days 被错误切成 37 blocks；而 #624 的 canonical block phase 来源于完整 frozen 2015-01-05..2020-12-31 Development 日历，共 1,462 个交易日，其中 ledger 窗口之前固定有 732 日，因此 ledger 首日实际位于原 block 的 phase 12，2018-2020 共跨越 38 个原始 blocks。

PR #650 只修复这一历史 block phase 的实现偏差，并同步 independent verifier 与 broker source hashes；没有修改预注册、目标、特征、阈值、horizon、context 或 authority。修复后：

- focused #647 suite：15/15 PASS；
- full public regression：1408/1408 PASS；
- synthetic Overnight BLACKBOX smoke：PASS；
- canonical ledger 本地 5000-draw analyzer 完成；
- independent verifier：PASS，29,713 rows / 38 blocks。

PR #650 merge commit 为 d536dcb42d3e36d0b0c24acef5691adbacfada29。第二次正式 governed run 35513990293-1 完整通过 prepare → credential-free compute → cleanup → private publish。

受控验收：

- public run：35513990293；identity：35513990293-1；
- public source SHA：d536dcb42d3e36d0b0c24acef5691adbacfada29；
- private receipt：passed / archive_uploaded_and_verified；
- private Release id：392443799；
- archive SHA256：2c2fefa2f3834df15016b3878f903d4d738429d456c4696c8c24674e6ea0bfd9；
- archive bytes：9,604；
- exact governed result SHA256：0149661b57a880e60227f0144d4713799f6c7bde5cc229b60f6536786337faa2；
- independent verifier output SHA256：1fb854e535ca7bf8613b34aca0d7cc7e4f0aa42fdb41e43499604f0ffe828e4e；
- verifier：PASS，verified_rows=29,713，verified_blocks=38；
- new_training=false；production_authority=false。

正式 result 与本地 canonical reproduction 有 5 个纯浮点末位差异，最大绝对差 1.11e-16，无任何非数值字段差异；governed independent verifier 对正式 JSON 自行重算并通过。不能把这种数值等价写成逐字节复现。

### 19.3 预注册机制门的正式结论

正式 label：MIXED_OR_INCONCLUSIVE。

四个 component 的 age-standardized Q5−Q1 与 interaction 呈现混合结构：

- risk_abs_ret_8：UP +6.43pp，DOWN +10.52pp；两侧均通过自身正向门，但 DOWN−UP interaction CI 跨零；
- risk_range_8：UP -2.36pp，DOWN +17.38pp；DOWN 与 interaction 通过，UP 不通过；
- risk_rv_8：UP -13.78pp，DOWN +15.51pp；DOWN 与 interaction 通过，UP 不通过；
- risk_efficiency_8：UP +15.19pp，DOWN +2.56pp；UP 通过，DOWN 与 interaction 不通过，且 interaction 方向为负。

因此 frozen component-coherent gate 的计数为：CURRENT_DOWN 3/4、CURRENT_UP 2/4、positive DOWN−UP interactions 2/4。它没有通过 COMPONENT_COHERENT_DIRECTION_ASYMMETRY，因为该标签要求 CURRENT_UP 最多只有 1/4 component 满足完整正向条件，而实际为 2/4。

age-composition 解释同样不足。frozen reference compression_score 的 raw DOWN−UP gap 为 0.20961，common-age gap 为 0.17868，age_gap_reduction_fraction 仅 0.14756，明显低于 AGE_COMPOSITION_DOMINANT 要求的至少 0.50；相关 bootstrap valid_draw_fraction 为 1.0。

因此当前证据不能把方向不对称压缩成一个单一局部机制，也不能归因主要是 carrier-age composition。它更像多个 frozen component 在 UP/DOWN 两侧作用方向不同的混合结构；#647 的设计本身不允许据此挑选赢家、重配权重或扩展新 feature family。

### 19.4 stop rule 与项目级含义

按 #647 预注册 stop rule，本门在 MIXED_OR_INCONCLUSIVE 后直接关闭：

- 不做 feature-zoo 扩展；
- 不把 range/rv 的 DOWN-side 结果改造成 DOWN-only trading rule；
- 不因本门混合就自动升级 P256/C2/C3；
- 不重启 future(C1) → future(C2) 递归；
- 不把 #624 重新分类为 supported；
- 不授予 signal/router/trade/paper/live/production authority。

当前框架级结论因此进一步收缩为：Local state-survival baseline 仍保留其已证明的信息性，但 UP/DOWN 非对称没有被一个冻结的单一 component-coherence 或 age-composition 机制解释；P128 current context 已由 #635 删除；任何后续新假设都必须有独立机制依据、重新预注册，并明确自己的负结果终止条件，而不能把 #647 当作继续搜索的许可证。
