# Two-Wave 5m Recognizer R2 正式裁决 — 2026-09-17

## 结论

R2 `ELIGIBLE_COUNTER_SHADOW` **不通过** #321 的 5m recognizer readiness gate，不能晋升为 detector repair authority，也不能据此开放 1m。

这不是因为 R2 没解决原问题。相反，它把 R1 剩余的 5 个非边缘 Q3/Q4 盲区、共 414 根 bar **全部恢复**，且没有制造新的 R1 盲区，所有相邻确认 pivot 的 occurrence gap 仍然 `>= MIN_LEG=4`。失败发生在另一端：R2 把“counter 的 occurrence 时间已经够远”错误地等同于“counter 已经成为成熟的反向极值”，造成系统性过切。

因此必须同时保留两个事实：

1. **R2 对 early-counter lock 的诊断方向是对的。** 独立的 eligible counter 确实消除了 R1 的五段残余盲区。
2. **R2 的修复语义过松。** 它把盲区问题换成了过分段问题，违反冻结的 no-oversegmentation gate，所以总体判决仍是失败。

## 正式运行身份

标准公开控制面真实运行：

- workflow run: `35163544010`
- private/public run identity: `35163544010-1`
- event: `workflow_dispatch`
- profile: `two-wave-recognizer-r2-eligible-counter-v1`
- public source: `6c18b886efa080cab03b4474df1d0ee657c2e7ec`
- private frozen source ref: `7688ba57206dd29fbef88d8e57475255718471fe`
- input: 000852.SH, 5m, consumed Development 2015–2020, 70,114 bars
- input SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`
- receipt: `passed`
- archive: uploaded and independently read back/verified

运行成功只说明 producer、独立 verifier、隔离执行和私库回存链路成功，不等于科学验收成功。

## R2 恢复了什么

R1 正式结果留下 5 个非边缘盲区、414 根 bar。R2 正式结果：

- non-edge blind episodes: `0`
- non-edge blind bars: `0`
- substantial Q3/Q4 blind episodes: `0`
- substantial blind bars: `0`
- R1 residual recovered bars: `414 / 414`
- R1 residual fully recovered episodes: `5 / 5`
- newly blind versus R1: `0` bars / `0` segments
- pivot occurrence gap minimum: `4`
- pivot gaps below MIN_LEG: `0`

所以 `ELIGIBLE_COUNTER_SHADOW` 的确解开了 R1 的 early-counter monopoly。

## 但 R2 为什么仍失败

冻结基线与 R2：

| 指标 | 4/48 baseline | R1 | R2 |
|---|---:|---:|---:|
| wave count | 2,503 | 2,704 | **4,345** |
| median duration | 21 | 22 | **14** |
| median amplitude | 0.010287 | 0.011090 | 0.008201 |
| median channel height | 0.006555 | 0.006800 | 0.005208 |
| low-amplitude share | 0.25010 | 0.23410 | **0.35489** |
| confirmation delay median | 4 | 4 | 4 |
| confirmation delay p90 | 7 | 7 | **4** |

R2 对 baseline 的冻结 anti-oversegmentation 控制：

- wave-count ratio = **1.7359**, 要求 `<=1.25` → FAIL
- median-duration ratio = **0.6667**, 要求 `>=0.75` → FAIL
- median-amplitude ratio = `0.7972`, 要求 `>=0.75` → PASS
- median-channel-height ratio = `0.7944`, 要求 `>=0.75` → PASS
- low-amplitude-share change = **+0.10479**, 要求 `<=+0.05` → FAIL
- confirmation-delay median change = `0`, 要求 `<=+4` → PASS
- confirmation-delay p90 change = `-3`, 要求 `<=+8` → PASS

因此：

- `no_oversegmentation=false`
- `numeric_gate_pass=false`
- `decision=REJECT_R2_FOR_5M_READINESS`

不得因为 blind fraction 已经归零就忽略这些失败项。

## 状态机层面的失败原因

R1 的问题是：一个发生在 candidate 后 1–2 根的 early opposite extreme 虽然不满足 `MIN_LEG=4`，却可能长期占住唯一 counter；如果后来没有出现更极端的 opposite close，它就永远不会被替换，最后触发 reset。

R2 为此增加了 `eligible_counter`，仅从 `candidate+4` 之后的 opposite bars 里取 counter。这个变化解除 early lock，但带来了一个新的逻辑等价：

> 只要到了 candidate 后第 4 根或更晚，第一根处于反方向的 bar 就能在同一根成为 eligible counter，并立即确认旧 pivot。

也就是说，R2 只证明了**时间距离够了**，没有证明这个 later counter 是一个**已经成熟的局部极值**。

正式 aggregate 的确认延迟给出很强的机制证据：R2 的 confirmation delay `Q25 / median / Q75 / P90` 全部等于 4。它已经接近“最小间隔 zigzag”，而不是在固定尺度上等待反向 extremum 成熟。

## OHLC 人工复核

视觉包强制包含全部 5 个 former-R1 residual case，另含 longest-wave control。

人工复核结果：

- 五段原有 Q3/Q4 盲区里的主要摆动被 R2 重新连出来；这支持 early-lock 诊断。
- 多个 former-R1 页面同时出现一串接近四根最小 occurrence gap 的短交替 L-H-L；这与全样本 wave-count 爆增、中位 duration 降为 14、一季度至九十分位 confirmation delay 都贴着 4 的统计结果一致。
- longest-wave control 中仍保留一条明显的长单边 leg，说明 R2 不是在任何路径上无条件每四根硬切；失败是**广泛的过度敏感**，不是简单固定采样。
- R2 visual renderer 还残留一句错误 legend：`vertical dotted = R1 confirmation`。实际绘制的是传入的 R2 candidate confirmation。这个标注缺陷不改变 aggregate 失败结论，但意味着本次 `geometry_evidence` 不能设为 true。

## readiness gate 状态

- coverage: PASS
- substantial_misses: PASS
- residual_character: PASS（无非边缘 residual）
- no_long_substantial: PASS
- **no_oversegmentation: FAIL**
- causality: source/independent verifier evidence存在，但本次 report authority 仍保持 false
- **geometry_evidence: NOT ACCEPTED**
- no_outcome_tuning: PASS

总体 numeric gate: **FAIL**。

## 下一步：R3，不修阈值

R2 失败后不允许放宽 #321 门槛，也不允许靠幅度/波动率/PnL 去筛掉多出来的波。

R3 已单独预注册为 issue #340：`MATURE_COUNTER_REARM`。

核心区分是两个因果时钟：

1. **pivot occurrence separation**：新 counter occurrence 与旧 candidate occurrence 至少相隔 4 根；
2. **counter extremum maturity**：counter 自己还必须在后续 4 根内不被更极端 opposite close 替代，才能被认为已经成熟。

如果一个 early counter 自身成熟后仍因为 occurrence gap <4 而不合格，则明确记为 `SUBSCALE_REJECTED`，随后重新武装一个新的 counter search。这样既不让 early subscale extreme 永久垄断，也不允许 candidate+4 的任意一根反向 bar 立即变成 pivot。

R3 不改变 `MIN_LEG=4`、`MAX_UNFINISHED_LEG=48`、R1 progress-aware reset、reset ordering 或 bootstrap；不增加市场调出来的幅度阈值。

## 权限边界

本次 R2 判决不开放：

- 1m admission
- signal authority
- detector-repair authority
- router authority
- trade authority
- production authority

失败候选 R2 必须保留在 lineage 中，不能由后续 R3 覆盖历史。
