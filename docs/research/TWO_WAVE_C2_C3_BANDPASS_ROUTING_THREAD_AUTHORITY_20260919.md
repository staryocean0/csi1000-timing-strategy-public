# Two-Wave 频段路由线程权威叙事：C2/C3 带通趋势状态 → T0/C1 双执行节奏

日期：2026-09-19。

## 当前阶段

本线程正式从此前的：

- C2 phase 语义阈值研究；
- T0/C1 自身状态机；
- 低通骨架 C2/C3 router；

转向新的研究架构：

> **趋势状态层使用显式带通残差 C2/C3；执行层只保留 T0/C1 两种交易节奏。**

当前主问题是：

> 当 C2 与 C3 的带通残差处于不同关系时，应该使用 T0 本频执行节奏，还是使用 T1/C1 一级低频执行节奏？

这份文档是本 Two-Wave 频段路由线程的最新权威叙事。它不替代 private 根目录 `CLOUD_CURRENT`，不改写其他研究线程。

---

## 1. 统一术语

为了避免“层级状态”和“交易节奏”继续混用，本线程采用以下命名。

### 1.1 低通骨架

原始对数价格记为 `X0`。

逐层低点骨架：

- `S0`：本频完整波低点骨架；
- `S1`：在 S0 上递归得到的更慢骨架；
- `S2`：在 S1 上递归得到的更慢骨架；
- `S3`：在 S2 上递归得到的更慢骨架。

S0/S1/S2/S3 统一称为**低通骨架**。

### 1.2 显式带通/残差分量

- `C0 = X0 - S0`
- `C1 = S0 - S1`
- `C2 = S1 - S2`
- `C3 = S2 - S3`

本线程状态机只研究：

- `B2 := C2 = S1-S2`
- `B3 := C3 = S2-S3`

它们是**带通/残差趋势状态输入**。

不得再把 S1/S2/S3 骨架上的 wave direction/phase 直接称为 B2/B3 bandpass state。

### 1.3 执行节奏

- `E0 := T0`：本频执行节奏；
- `E1 := T1/C1`：一级低频执行节奏。

E0/E1 是**状态机动作/输出**，不是状态输入。

---

## 2. 为什么必须转向

相邻频段的真实周期比并不是固定 2–3 倍，但已测得：

- T1/T0 中位约 3.71；
- T2/T1 中位约 3.08；
- T2/T0 中位约 13.60。

相邻约 3–4 倍尺度处于尴尬区间：

- 当较慢相邻频段的信号被确认时，它自身可能已经接近转折；
- 因此不能简单用 C1/T1 去“指导” T0；
- 同理，任意相邻尺度之间都可能出现 supervisor/follower 两头挨打。

因此 T0 与 T1/C1 必须视为互补执行节奏，而不是上下级预测关系。

相反，更慢的 C2/C3 趋势状态可以作为背景，决定当前应该采用快节奏还是慢节奏。

---

## 3. 为什么状态机输入要用带通而不是低通

如果直接比较低通骨架 S2/S3：

- 两者都包含更慢层的信息；
- 大量共同低频成分会使状态关系高度相关；
- 难以分辨“这一层自己在起作用”还是“更慢趋势共同推动”。

因此采用残差思想：

- C2 先剥掉 S2 之后只保留 S1 到 S2 之间的尺度成分；
- C3 再剥掉 S3，只保留 S2 到 S3 之间的尺度成分。

状态机研究对象是：

> **C2 自身的带通状态 × C3 自身的带通状态**

而不是两个带着共同更慢趋势的低通方向。

---

## 4. 当前已经确认的事实

### 4.1 层级与尺度

冻结 Development 数据：

- 000852.SH
- 5m
- 2015–2020
- 70,114 rows
- SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

scale-specific continuity 当前递归容量：

- stage1 stream nodes: 2,648
- stage2 stream nodes: 673
- stage3 stream nodes: 171
- stage4 stream nodes: 40

显式带通 occurrence 支撑：

- C2=S1-S2：69,615 bars
- C3=S2-S3：68,911 bars
- C2/C3 joint：68,911 / 70,114 = 98.28%

因此“显式 C2/C3 带通研究”在回顾表示层面具有足够物理支撑。

### 4.2 已经降级的旧结论

以下历史证据保留，但不再承担当前主叙事：

1. C2 deadband `exit=0 / enter=0.01`
   - 只保留为 minimum anti-chatter buffer evidence；
   - 不是 C2 semantic RANGE 真值。

2. dense retrospective C2 +8 persistence
   - 其 UP/DOWN 极高持续率受 S1/S2 线性插值长段影响；
   - 不再解释为 causal delayed-following value。

3. base/current-band 单波 slope -> C2 semantic phase
   - 已判 `BASE_SLOPE_ALONE_INSUFFICIENT_FOR_C2_SEMANTIC_PHASE`。

4. T0/C1 自身状态机
   - T0/C1 是执行节奏，不是趋势状态输入；
   - 该方向不再作为主状态机研究线。

5. 旧 C2/C3 router
   - 主要使用递归骨架 wave state；
   - 不等同于本线程显式 C2/C3 bandpass residual state。

---

## 5. 新研究问题

只回答一个核心问题：

> **显式 C2 与 C3 带通残差之间是否存在稳定的趋势状态关系，可以决定当前应采用 E0=T0 还是 E1=T1/C1 的执行节奏？**

首轮不假设：

- 九格一定正确；
- sign 一定是最重要变量；
- phase 一定有效；
- C2/C3 必须同向/反向；
- 某个固定阈值必然存在；
- 某个模型族一定可行。

先找规律，再冻结候选状态机。

---

## 6. 研究顺序

1. **Representation freeze**
   - 构造显式 S1/S2/S3 与 C2/C3；
   - 验证 common support、重构关系、确定性、边界；
   - 不看 T0/C1 outcome。

2. **Bandpass morphology atlas**
   - 只描述 C2/C3 自身；
   - sign、局部 slope、turn、amplitude、pace、phase、zero-crossing、lead-lag；
   - 不选交易规则。

3. **Causal observability gate**
   - 检查哪些 bandpass 状态在实时知识边界可得；
   - prefix replay / evidence age / confirmation lag；
   - 回顾 oracle 与 causal carrier 分离。

4. **Execution contract**
   - 明确 E0=T0 与 E1=T1/C1 各自的触发、持有、退出生命周期；
   - 禁止固定 T0 窗口后让 C1 只做反向影子来冒充完整模块比较。

5. **Relationship-to-execution atlas**
   - 在冻结的公平 E0/E1 比较合同下；
   - 研究 C2/C3 bandpass relation 与哪种执行节奏更适合之间的关联；
   - 仍然只做 discovery。

6. **Candidate state-machine preregistration**
   - 只有发现稳定规律后才冻结状态机；
   - walk-forward / cluster uncertainty / no post-hoc cell merging。

7. **Independent validation**
   - development 结果不能升级为 production；
   - fresh OOS / 独立时间段另行冻结。

---

## 7. 研究边界

当前没有：

- 状态机赢家；
- C2/C3 bandpass 数值阈值；
- T0/C1 路由规则；
- route PnL authority；
- paper/live/production authority。

所有新 outcome-bearing 研究必须在表示和执行合同冻结之后进行。

---

## 8. 当前线程状态

`BANDPASS_TREND_STATE_TO_EXECUTION_RHYTHM_DISCOVERY`

主 issue：#450。

当前下一步：

`R0_EXPLICIT_C2_C3_BANDPASS_REPRESENTATION_FREEZE`
