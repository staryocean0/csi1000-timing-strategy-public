# #363 盲化参考包 v2：anchor-context 资格前置

v1 正式运行 `35205287251-1` 在任何 panel、标签或 dominance 分数生成前，因选中上下文包含 `causal_flat_fill` 而 fail-closed。失败回执/归档保留，不重跑、不改写。

v2 不允许“抽中以后换日期”。先对 #352 的共同完整日计算同一个确定性 anchor，再检查该 anchor 向前 300 个合格交易分钟：必须完整、全部 `high_frequency_analysis_eligible`、全部无 `causal_flat_fill`，并且五套 5m phase 都至少有两根完整 constituent 落在同一 300 分钟支持内。

只有满足上述条件的 anchor-day 才进入候选池，然后按新命名空间 `csi1000-s2-ref-v2` 在每季度取最低哈希的 8 天，共要求 192 个 panel；任一季度不足 8 个则整轮失败。panel id 同样使用 v2 命名空间，anchor hash 保持 v1 不变。

该修正只针对 reference support population，不依据振幅、波形、R1/R2/R3、诊断分数、收益或结果。Pass A/B 的盲化、标签体系、歧义规则、未来后缀不回填和失败样本后置审计规则保持 #359 不变。

新 profile：`two-wave-scale-reference-blind-packet-v2`。当前状态：**REGISTERED_NOT_RUN**。真实运行仍只能通过审核后的标准 `workflow_dispatch`。
