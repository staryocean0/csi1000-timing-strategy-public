# 双向验证：正式执行与私库证据索引（2026-09-16）

本条仅保存本线程的控制面进度，不公开私有市场研究数值，也不覆盖项目CLOUD_CURRENT。

研究脉络：#273将单波和九格持久化；#279定义已确认低点骨架及背景时钟；#289在用户要求下分别实现A看小做大与B看大做小，并冻结单一待执行版本。旧候选包不作为第二套结果择优。

## 已完成的执行链

最新head bb84a60931fb3d4caa99629d5ad02842059a27b0 的两条Ubuntu CI均通过，专项73项无skip。PR #289合并为e9ec03919df6fd45b47709249915c0007c9660c2。
唯一controller issue #299发起标准run 35065802258-1；事件workflow_dispatch、活动分支cloud-workspace-v1、profile two-wave-dual-gates-v1、source SHA均一致。prepare、compute/verify、cleanup、private publish全部success。

私库快照1cf70f05c087fa6b3be673d53fc1b1808f8dc1cf：receipt research/public-runs/35065802258-1.json；aggregate research/public-runs/35065802258-1/report.json；同目录execution_manifest.json。receipt passed，archive_uploaded_and_verified。私有release389694986的资产567385556，字节数与服务端digest和receipt一致。精确哈希见同名JSON索引。

## 怎样阅读结果

技术执行成功和科学验收不同。A.verdict、B.verdict及敏感性结果只从私库report读取；先看support、覆盖、缺失背景、时间块和逐年数量，再解释评分或收益代理。INCONCLUSIVE不等于已经证伪；未发生交易的零收益也不能解释成减少打脸有效。

原始核验含独立pivot kernel、概率表、标签和成交检查及A/B前缀抽查；整份报告重执行只叫可复现，不宣称所有统计逻辑独立重写。此轮数据为已消费Development，不叫fresh OOS。Chat只复核private aggregate，没有读取行级行情/状态/交易账本用于调参。

本次执行与结果回读已完成，固定试验不做结果后修参；后续方向应另行预注册。#274和#277的其他频率、视觉、推断门不随本条自动关闭。交易、状态发布和生产权限仍为false。研究配置、结果与失败证据均保留。
