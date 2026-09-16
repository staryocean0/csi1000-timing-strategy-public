# Two-Wave 双向决策验证：正式市场裁决（2026-09-16）

本文件记录 `two-wave-dual-gates-v1` 的真实 Development 市场执行结果。它与源码/合成测试通过、正式 workflow 执行成功、科学支持、交易权限分别记录，不能互相替代。

## 1. 执行身份

正式 public run：`35065802258-1`；public source：`e9ec03919df6fd45b47709249915c0007c9660c2`；标准入口 `.github/workflows/public-compute.yml`、事件 `workflow_dispatch`、分支 `cloud-workspace-v1`、profile `two-wave-dual-gates-v1`。

prepare、无凭据 compute + verifier、cleanup、private publish 全部成功。私库回执状态 `passed`，结果 archive 上传并回读验证；`new_training=true`、`production_authority=false`。

固定数据仍为 000852.SH 的 2015—2020 `5m_offset_0` Development，70114 rows，SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`。这些年份已被消费，不能称 fresh OOS。

基础波重建与旧冻结结构一致：5471 pivots、2503 complete A-waves、164 resets。

## 2. Gate A：看小做大

问题：在当时已经可知的大级别背景之上，加入小级别两波九格、相对振幅和单波内部形状，是否能改善对之后新发生的大级别 swing turn 的判断？

最终 verdict：**INCONCLUSIVE，点估计为正，但支持度远远不够。**

924 个 same-scale strict pairs 中，形成前已知大背景只有 199 个：UP 117、DOWN 82；另外 725 个为 UNKNOWN，占约 78.5%。这是本门最明显的结构性瓶颈。

A 的事件损耗：1434 个 scale mismatch；707 个没有可识别父背景；56 个右截断；161 个标签最终 settled。真正进入 2018—2020 walk-forward 评分的只有 32 个，正类 10 个，11 个父结构组；边界 purge 后只剩 21 个 inference events 和 3 个时间块。2018 没有可评分事件，2019 有 25 个，2020 只有 7 个。

点估计方向如下：

| 模型 | Brier | LogLoss |
|---|---:|---:|
| A0：仅父背景 | 0.233671 | 0.659632 |
| A1：+ 九格和相对振幅 | 0.231054 | 0.654352 |
| A2：+ 单波内部形状 | 0.229510 | 0.651217 |

也就是说，A1、A2 相对 A0 的 pooled 点估计都在改善，内部形状相对于 A1 也继续改善一点。但预注册要求至少 200 个可评分事件、正负类各 30、30 个父波组和 30 个时间块；真实结果离这个门槛很远，区间无法计算。

因此本研究**不能接受“九格/内部形状能预测大波拐点”**。但它也不是负结果：目前最强限制来自 causal parent-context coverage，而不是观察到模型恶化。

后续处理：**保留 A 作为优先研究候选，但不接受为信号。**如果继续，应先提高父背景在不偷看未来前提下的可识别覆盖，并保持当前目标/阈值冻结；不能围绕这 32 个样本继续调参找规律。

## 3. Gate B：看大做小

问题：若 2—3T 的中间周期占主导，当前 T 周期的趋势跟踪是否更容易被来回打脸；若明显更慢的 >=6T 结构占主导且方向对齐，趋势策略是否更稳定？

最终 verdict：**INCONCLUSIVE，而且这次没有真正进入经济假设比较。**

2018—2020 基准趋势机会有 949 笔已结束交易；T=21 bars。基准 fast-loss rate 约 39.8%，连续双向 fast-loss rate 约 15.3%。这些只是固定诊断策略的基线，不构成交易权限。

关键问题在背景解析：

- `INSUFFICIENT_HIERARCHY`：849 笔；
- `NO_ROOT`：100 笔；
- 可解析为 2—3T / 3—6T / >=6T 的 entry：**0 笔**；
- strength cutoff：无法形成；
- selected trades：0；
- coverage：0%。

`min_leg_nodes=1` 的主版本和 `min_leg_nodes=2` 敏感性版本都得到同样的零覆盖。因此，没有任何有效的“2—3T 主导 vs >=6T 主导”样本可比较，adjusted mechanism 也只能返回 `INSUFFICIENT_COMMON_SUPPORT`。

报告中的 filtered net=0、filtered-minus-baseline 为负，只是因为过滤器一笔都没选中；**不能解释为“大周期背景会让策略更差”。**反过来也不能解释为有效过滤。这个结果证明的是：本次多级图形 hierarchy 的可用性不足，未能把用户要检验的频率背景投影到实际交易机会时点。

后续处理：**暂停 B 的经济验证。**若继续 B，必须另立一个“hierarchy availability / scale identification”研究门，先证明在 entry 时点能够稳定识别 2—3T、过渡和更慢背景，再重新预注册 B2；不能在本 study 身份下事后放松 dominance、层数、staleness 或周期门槛救 coverage。

## 4. 两条路线的当前取舍

这次没有得到“两条都通过”或“一条明确失败”的干净答案。

- **A：值得继续，但仅作为研究候选。**点估计方向一致地偏正，问题是证据太少。
- **B：当前实现不能评价假设。**不是经济负结果，而是上层图形表示没有覆盖到实际机会。

因此下一步优先级是：

1. **优先继续 A**：做父背景覆盖/识别完整性研究，而不是换目标或调模型；目标是让真实可评分事件达到足够规模，再重复同一类 walk-forward 增量比较。
2. **B 只保留为工具层修复线**：先单独验证多级图形是否能在实时点识别 2—3T 与更低频结构；通过覆盖与图形验收后，才允许重新开启经济 Gate B2。

这不是“选择 A、永久放弃 B”。它表示当前证据下，A 已出现值得继续验证的弱信号，而 B 尚未形成可被检验的研究对象。

## 5. 权限与叙事边界

本次不授予 direction acceptance、state publication、trade 或 production authority；baseline trend proxy 的开发期正收益也不能拿来作为策略通过证据。

不得把 run success 写成 A/B scientific success，不得把 B 的零覆盖写成 top-down 假设失败，不得把 A 的 32 个 OOF 样本写成预测规律已成立。

后续文档必须保持顺序：单波工具 → 九格 → 已确认低点骨架 → 双向 Gate 预注册 → 正式 run/receipt → 本裁决 → 下一轮另行预注册的问题。失败、样本不足和零覆盖均作为研究脉络的一部分保留。
