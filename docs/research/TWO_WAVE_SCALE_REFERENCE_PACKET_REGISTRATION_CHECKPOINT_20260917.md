# #359 真实盲化参考 packet：注册检查点

当前阶段只把已经冻结的参考协议接到标准执行链，**尚未运行真实 packet，也没有生成任何真实参考标签或 dominance 分数**。

固定 profile：`two-wave-scale-reference-blind-packet-v1`。它复用 #352 已资格通过的六份固定 Development 载体与原 public staging，不新增数据来源。

每个预注册锚点只生成三张图：

- `A150`：锚点前 150 个共同支持交易分钟的 1m close 归一化形状；
- `A300`：锚点前 300 个共同支持交易分钟的 1m close 归一化形状；
- `B300`：同一 300 分钟上下文内五套 5m offset 的归一化 low/close/high 几何。

192 个锚点，因此固定 576 个 SVG。真实日期/季度/锚点到 panel id 的 full inventory 只留在私有结果包；blind inventory 和 SVG 不显示日历日期、R 版本、候选输出、诊断分数或收益。
如果预注册锚点无法取得完整 300 分钟共同支持、上下文包含 `causal_flat_fill`、或任一五相位视图缺失，运行直接失败；不换日期、不换锚点，也不靠后验选择样本补洞。

producer 负责生成 packet；runtime verifier 不导入 producer/entry/renderer/dominance diagnostic，而是从固定载体独立重建共同支持、192 个 panel identity、相对时间上下文以及 SVG 几何，再逐文件核验 manifest。

标准工作流仍只有原来的两处私库凭据边界：prepare 与 publish。compute/cleanup 不携带私库 token。详细 panel 通过通用私有 result archive 回存；额外镜像只允许 `packet_summary.json`。

这一步不改变旧 #321，也不把 R3 改成成功；不选择 R4、不产生 1m 策略、不做 router/PnL，也没有生产权限。

下一步只有在本 profile 的 PR 最新 head CI 全部通过并合并后，才创建 exact controller issue 触发真实 `workflow_dispatch`。真实运行本身仍然只生成盲化 packet，不计算 dominance score。
