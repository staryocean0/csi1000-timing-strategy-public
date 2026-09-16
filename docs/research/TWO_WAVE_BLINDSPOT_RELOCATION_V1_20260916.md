# Two-Wave blindspot relocation V1

本研究是 scale-specific continuity 通过表示门以后，对 5m 识别器做修复前的最后定位诊断。

冻结对象不变：000852.SH 5m 2015–2020、base detector 4/48、旧 identifiability V1 的 146 个 blind episodes，其中 144 个 RESET_ROOT_BREAK；不引入 1m，不改 pivot kernel，不读取收益、PnL 或 router outcome。

continuity 已把高层表示从 hard-root 的 C1/C2/C3=473/46/1 恢复到 672/170/39，且 frozen base ledger 不变。因此本轮只问：原先的大振幅盲区，在连续 C2/C3 中物理上究竟处在哪里？

保留两张完全分离的图。Retrospective map 使用完整确认后的 C2/C3 occurrence geometry，只解释物理位置；causal as-of map 只使用当时已经确认的 C2/C3 descriptor、leg、phase、amplitude、age 和 lower-reset crossing metadata。事后标签不得作为实时状态回填。

主统计量是 exposure-normalized blindness：每个状态的 blind fraction 以及相对于全样本 blind fraction 的 lift。不能因为某个状态本来占据大多数市场时间，就把较多 blind bars 错认成失明机制。

若大振幅盲区稳定富集在某个因果状态，可据此预注册下一版 recognizer repair；若盲区跨相位广泛分布、但只与 reset/root crossing 强相关，则下一步应修 base 级 continuity，而不是制造一个“顶部/底部信号”。若最终残余盲区主要属于 Q1 小振幅，则保留 abstention 可能是正确行为。

本轮不授权任何 detector repair。任何修复候选必须在看到自己的真实 aggregate 结果之前单独注册，并继续接受 #321 的 5m readiness gate：non-edge blind bars <=2%，Q3/Q4 blind episodes <=5、blind bars <=0.25%，残余 blind episodes >=90% 为 Q1，同时禁止过分割救覆盖。
