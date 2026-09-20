# Model B / #635：当前 P128 上下文的 structural state-exit 条件增量预注册

日期：2026-09-20。状态：`PREREGISTRATION_BEFORE_MODEL_B_OUTCOMES`。
机器合同：`TWO_WAVE_MODEL_B_P128_STATE_EXIT_PREREG_20260920.json`。
先读同名前缀的 AUDIT 文档；本文件与 JSON 一起冻结，冲突必须在新 outcome 执行前解决，不能事后择其有利者。

## 1. 唯一问题与范围

在同一知识时点、同一 #624 Amendment-A structural state-exit 目标与同一可比总体上，控制本频方向、冻结 carrier-age bins 和原 label-free compression score 后，P128 当前已知 raw-price phase 是否还有稳定增量？
不预测下一个方向，不计算 PnL，不改变 #507/#615/#624，不使用 future(C1/C2/C3)。一个 context、一个模型族、一个 primary horizon；不同时试 P256、stage1 leg 或不同窗口再选优。
P128 不是显式 C1，不是证明了尺度分离的带通信号。本研究回答这个有限表示是否优于指定 A，而不是证明更慢频段是市场因果驱动。

## 2. 数据、资格与冻结目标

固定 000852.SH、原生5m、2015–2020，70,114 rows / 3,351,411 bytes；SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`。来源与不可变 ref 见 JSON。既有全部 development 暴露事实保留，不称 fresh OOS。

accepted wrapper 在 k 输出 CURRENT_UP 或 CURRENT_DOWN 才有资格。pre-veto carrier 的64-close view、FROZEN_WEIGHTS、±0.20 阈值与连续 carrier age 完全不变。
`y8=1` 当且仅当 carrier 在 k+1..k+8 第一次离开当前方向；进入 DIR_RANGE 或相反方向均算退出。LOW/FINER exact-label 跳转不参与 primary。
同样保存 `y16`，但只作未来 +16 风险分离诊断，不另拟合或挑选第二个概率模型，不救 primary 失败。
最终评价仍使用 #624 的 +16 完整终端支撑与2018/2019/2020知识年份，预期29,713行。复核旧 ledger 的行键、state、age、target、score/bands及 canonical identity；这仅是继承身份检查，不重做 #624 的科学门。

## 3. 不含未来结果的 decision stream

每个 k 的 state、carrier age、四项 local features 和 P128 只读 <=k。预测函数不要求 k+8/k+16 已经存在。
先产生 decision stream 与 label-free prior-year score，再做 context coverage，最后才训练/评价。最终评价的终端支撑过滤不能反向改变 feature/CDF/calibration。

四项 raw compression feature 及 reverse percentile/等权/risk_band 规则复用 #624。对测试年 Y，CDF reference 是全部 knowledge_year<Y 的 eligible decision rows；不因 context 缺失或训练标签 purge 删除该 label-free reference。

## 4. 唯一 context 合同

输入 `close[k-127:k+1]`，调用已冻结 #429 parent_phase。
UP/RANGE/DOWN 以原 normalized OLS migration ±0.20 划分；flat log span<=1e-15 是有效 RANGE，不是假定趋势终止。
相对本频 CURRENT_UP/DOWN 映射 ALIGNED/NEUTRAL/OPPOSED。保留三类，不事后合并 NEUTRAL 与 ALIGNED。
缺历史或非法 context 输入记 `UNRESOLVED` 及原因；不能填成0、NEUTRAL或偷偷删行。

在新 outcome 比较前报告全资格集的 coverage、missing reason，按年份、方向、age-bin、原 compression band 分布。若共同支撑不足，按已冻结门停止，不换 context。

## 5. A/B：同一个有限概率校准族

令 s 为 direction×age-bin 的10个固定 cell；q=compression_score−0.5。

A 的 logit：
`a_s + b_UP*q*I(UP) + b_DOWN*q*I(DOWN)`。
共10个 cell intercepts +2个方向特定 slope=12参数。

B 在同一设计上增加4个参数：
`direction × I(context=NEUTRAL)` 和 `direction × I(context=OPPOSED)`；ALIGNED 为参照。
B 共16参数。B 的 shared coefficients 重新拟合，但设计、数据、算法、正则与 A 对称；不添加 context-age/score 交互、连续g值、窗口族或额外特征。

这是嵌套而非完全相同参数数量的比较；额外自由度明确限为4个，不用更大的模型或训练内拟合优度证明增量。
两个模型分别最小化：
`mean(logaddexp(0,eta) - y8*eta) + 0.001/2 * sum(penalized_beta**2)`。
10个 cell intercepts 不惩罚，其余全部系数使用相同 ridge penalty。固定 Newton/backtracking，gradient infinity norm<=1e-9，最多200次迭代；不收敛是工程失败，不换算法族或调lambda救结果。
概率用于评分时统一clip到[1e-6,1−1e-6]；无 post-hoc 概率修正。

A、B 都是新 supervised probability comparison layer，`new_training=true`。原 #624 compression score仍label-free，其历史裁决不被改写。
不能把 B 相比原始未校准 compression 的总改善全部归给 context；核心只看 B_calibrated−A_calibrated。

## 6. 年度 prior-only 训练和成熟时间

仅2018/2019/2020三次年度切分，每年分别拟合 A/B，不在年内更新。
令 c_Y 为第Y年第一个原生bar下标。训练标签只允许 `k+8<c_Y`。即使尚未成熟的标签事后可见，也必须 purge；报告每折被purge的行数、最大训练 feature/label index和截止点。
A/B 使用同一批 prior-year、context-resolved、label-mature 的资格行。相同的 prior-year CDF reference 先转换训练/测试 compression；训练分数是截止点可知的参考分布表达，不声称它是该训练行在旧知识时点曾真实发布的预测。
未来标签只在成熟的 prior training 中拟合、或在测试评价中使用，不进入当时 context/feature/CDF。

## 7. 缺失与共同支撑

主评价保留完整 #624 集合。context unresolved 时 B=pA 精确回退，保留预测和缺失标记，不额外训练 missingness 模型。
另在同一个 resolved common-support 子集同时重评 A/B，并报告全集与子集的分母及差异。
两模型训练时的 common-support 排除、标签成熟 purge 与 evaluation missingness 分开记账。

Support 必须全部满足：
- 原样本与冻结源身份准确；总 scored>=20,000，至少30个20交易日块。
- 每年>=5,000；每个方向×年>=1,000。
- 每个方向×年 context coverage>=95%；每折 mature-prior context coverage>=95%。
- 每个方向×relation pooled>=300行且覆盖>=15个时间块。
- 每个训练 direction×age cell>=100行、>=10个退出与>=10个不退出。
- 每项主要 bootstrap CI 至少4,750/5,000个有效draw。
不足为 INSUFFICIENT_SUPPORT，不悄悄并桶或放宽。

## 8. 配对评价与不确定性

Primary gain：`d_Brier = mean((y8-pA)^2 - (y8-pB)^2)`，越大越好。
Relative gain：`d_Brier / Brier_A`。
Secondary corroboration：`d_logloss = mean(logloss_A-logloss_B)`。
所有比较必须逐行配对；不是分别bootstrap后相减。

继承 #624 的20-trading-day calendar block构造（不按有信号日压缩日历），5000次有放回整块重采样，seed=20260920。每次共用同一组块权重计算 A/B、方向与全年样本的 loss 差。
年度 fitted models 不在 bootstrap 内重新拟合，因此 CI 是条件于这六个冻结年度fit的评价不确定性，不完整覆盖设计选择/训练不确定性。保留约38块的限制，不将29,713行视为独立交易。

同时报告：pooled、每年、UP/DOWN、8个 k mod8 cohorts、common-support 的 Brier/logloss/AUC与增量；方向与 pooled 的 loss CI；context cells 的支持。
固定10个等宽 probability bins [0,0.1,...,1]，报告 reliability、ECE、mean prediction−observed rate；空bin显式报告而不换分箱。
风险分离使用每模型每折的 prior-training prediction quintiles，在测试上报告低/高桶 y8与y16风险；不得拿测试期重新选桶，也不将这些桶当作旧 #624 B1..B5 或交易阈值。

## 9. 冻结信息门

全部 support 与 causal/identity checks通过，且以下全部成立才为 `MODEL_B_P128_STATE_EXIT_INCREMENT_SUPPORTED`：

1. pooled relative Brier gain>=1%；这个最低实际增量是本次研究选择，不是交易收益门。例：A Brier=0.20时要求绝对gain>=0.002，不是准确率增加1个百分点。
2. pooled Brier gain 的95% block-bootstrap下界>0。
3. pooled log-loss gain 的95%下界>0。
4. UP和DOWN各自 Brier gain 的95%下界均>0；不靠只保留一侧通过。
5. 三个测试年 Brier gain全部>0。
6. 至少6/8个固定overlap cohorts的 Brier gain>0。
7. pooled ECE_B−ECE_A<=0.005。
8. resolved common-support 的 Brier gain>0。

支持充分但任一信息门失败：`MODEL_B_P128_STATE_EXIT_INCREMENT_NOT_SUPPORTED`。
支持不足：`MODEL_B_P128_STATE_EXIT_INCREMENT_INSUFFICIENT_SUPPORT`。
AUC和+16诊断不能覆盖失败的 primary gate；没有事后降低门槛、改ridge、合并context或删除UP的许可。

## 10. 新链因果验收与 independent verifier

固定prefix lengths：10000/30000/50000/65000；另在每个测试年首bar长度+1与+9核验跨年purge边界。
对已可知的 state、carrier/age、local features、context、CDF score/band、年度fit rows/coefficients、pA/pB逐项比较。尚无测试年的早期prefix只核对可定义部分，不伪造预测支持。
在长度50000、65000之后对未来OHLC施加确定性非平凡扰动，<=cutoff已经发布的全部对象不应改变；允许之后的outcome改变，但不能进入旧预测。
合成测试包含未成熟跨年标签污染、未来suffix变动、flat与非法context、missing fallback、对称fit样本、配置不可变、负gate与支持不足。
Independent verifier不能导入新的producer study；可复用已冻结的legacy recognizer/wrapper/score定义作为已接受依赖，但须独立重建新context/fit/配对损失与判定，并核对实际输出字段/哈希，而非只读status。

## 11. 执行与停止

本预注册先经审查合并，再开发和登记唯一固定profile，经公库标准workflow_dispatch执行 prepare→无凭据compute/verify→cleanup→私库publish→controller回读。
本文件不授权本地任意私密研究、任意private写入或替代标准runner。实现、profile、verifier与固定source manifest未冻结前不能运行新市场outcome比较。

B不支持则停止并不保留P128作为已通过的预测增量；不自动转P256/C2/C3。B支持则冻结证据，经济干预仍需另一份事前合同。
两种结果都不改写旧 #624、不说明所有单频段/跨频段方案可行或不可能。统计预测损失改善也不等于真实市场趋势物理结束、盈利退出或零延迟能力。
本轮 signal/router/trade/paper/live/production/economic-intervention authority 全部为false。
