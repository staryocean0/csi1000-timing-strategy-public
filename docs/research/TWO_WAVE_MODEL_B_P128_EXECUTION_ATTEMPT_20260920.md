# Model B / #635：首次 governed execution 工程失败记录

日期：2026-09-20。
状态：`ENGINEERING_TIMEOUT_FAILURE__NO_SCIENTIFIC_VERDICT`。

## 1. 运行身份

- 标准 workflow：`.github/workflows/public-compute.yml`
- 事件：`workflow_dispatch`
- profile：`two-wave-model-b-p128-state-exit-v1`
- public run：`35499292209`
- run identity：`35499292209-1`
- public source SHA：`2e276dff8645015addbe3c58d621408f52ee6391`
- private source ref：`2815f50b5a1b2925f0e0118b0af0d578605ee882`

Prepare 成功；compute/verify 失败；cleanup 成功。
失败证据通过既有 broker 回存到私库，未将私密研究输出暴露到公库。
## 2. 私库失败回读

private receipt：
`research/public-runs/35499292209-1.json`
（结果分支 `runs/public-research/35499292209-1`）

receipt status：`failed`
delivery：`archive_uploaded_and_verified`

Private Release：
- release id：`392365377`
- tag：`public-research-run-35499292209-1`
- archive bytes：`744`
- archive SHA256：
  `45318072c289413b447048bfb25ac0bdeb42c27db5037d072fee08362ad4c3e2`

归档中的 `compute.log` 与 `container.log` 均为0 bytes；
独立 verifier 日志显示 `ISSUE635_RESULT_EXACT.json` 不存在。
## 3. 根因

通用 broker 的 host-side compute watchdog 固定为660秒：

`COMPUTE_HOST_TIMEOUT_SECONDS = 660`

而 #635 profile 当时声明 producer/validator 各2400秒。
公开 workflow compute step 的总上限为35分钟。

run 35499292209 的 compute 从约08:23:32 UTC持续到08:34:34 UTC，
即约662秒后被 host watchdog 终止。producer 尚未完成结果落盘，
随后 verifier 因 exact result 不存在而失败。

因此这是执行时间边界不一致的工程失败，不是：
- support gate 的 `INSUFFICIENT_SUPPORT`；
- Model B 的 `NOT_SUPPORTED`；
- 独立 verifier 对已存在科学结果的否决。
## 4. 最小修复

只调整 #635 专用 broker：
- producer command timeout：900秒；
- verifier timeout：900秒；
- #635 host-side watchdog：960秒。

通用 `research_broker.py` 默认660/210秒不修改，
其他 profile 的边界不变化。900+900秒的内部上界仍低于
标准 workflow compute step 的35分钟总预算，并给 host watchdog
留60秒用于写有界失败收据。

新增 profile regression 验证专用 timeout 配置和通用默认隔离。

本地验收：
- #635 timeout 专项测试：PASS；
- 全仓 unittest：1389/1389 PASS；
- synthetic Overnight BLACKBOX smoke：PASS；
- 测试前后相关源码 SHA 未变化。
## 5. 科学与权限边界

本修复不改变：
- #624 Amendment-A structural state-exit target；
- P128 当前 raw-price context；
- A/B 12/16参数设计；
- ridge、bootstrap、信息门、数据范围；
- 任何 signal/router/trade/paper/live/production 权限。

run 35499292209 永久保留为工程失败证据。
必须由修复后的合并源码重新发起新的 genuine `workflow_dispatch`，
并完成独立 verifier、cleanup、私库 publish 与回读后，
才能产生 #635 的科学裁决。
