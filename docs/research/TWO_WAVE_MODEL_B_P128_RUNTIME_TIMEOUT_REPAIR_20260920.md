# Model B / #635：首次 governed run 运行时限与 receipt 元数据修复

日期：2026-09-20。状态：`ENGINEERING_REPAIR_BEFORE_CANONICAL_REPLAY`。

## 失败运行的身份

首次标准 `workflow_dispatch` 运行：`35499292209` / identity `35499292209-1`。
public source SHA：`2e276dff8645015addbe3c58d621408f52ee6391`。
profile：`two-wave-model-b-p128-state-exit-v1`。

prepare 成功；compute 失败；cleanup 成功；失败证据随后由 publish 回存并回读验签。
private failure receipt 位于：
`runs/public-research/35499292209-1:research/public-runs/35499292209-1.json`。
private Release id=`392365377`，archive SHA256
`45318072c289413b447048bfb25ac0bdeb42c27db5037d072fee08362ad4c3e2`。

## 这不是科学负结果

回存 archive 中 `compute.log`、`container.log`、`controller_validation.json`
均为0 bytes；没有 `ISSUE635_RESULT_EXACT.json` 或 scored ledger。
verifier 唯一可见错误是找不到上述 exact result 文件。
因此本运行没有形成可裁决的 Model B 市场结果，不得记为
`MODEL_B_P128_STATE_EXIT_INCREMENT_NOT_SUPPORTED`。
## 根因

共享 `research_broker.py` 的 host watchdog 仍固定为：
- compute：660秒；
- validate：210秒。

#635 专用 profile 当时声明 producer/verifier 各2400秒，但 custom broker
直接调用共享 `rb.compute()`，没有覆盖共享 host watchdog。
实际 compute 从 08:23:32 UTC 运行至 08:34:34 UTC，约662秒，
与660秒 host watchdog完全吻合；wrapper 被 host 强制清理后没有结果文件。

标准 workflow 的 Compute step 自身固定35分钟，因此原“2400+2400秒”
profile 与共享 step budget 也不一致。修复只调整执行时间预算，
不改变 target、P128 representation、A/B 参数、ridge、support gate、
bootstrap、数据或任何科学 acceptance 条件。

## 修复

仅在 #635 专用 broker 内：
- producer timeout 固定为900秒；
- verifier timeout 固定为900秒；
- 对两阶段 host watchdog 均固定为960秒；
- 共享 broker 默认值和其他 profile 不变。

900+900秒加上两个 bounded host 缓冲仍处在标准35分钟 Compute step 内。
同时修复 #635 私库 run receipt 的训练属性。
共享 legacy publisher 会把 receipt 的 `new_training` 固定写为 false，
而 #635 预注册明确 A/B 是新的 supervised probability layer，
必须记录 `new_training=true`。

为避免改动共享 publisher 及历史执行 manifest，
#635 专用 broker 在 publish 已成功创建并回读 receipt 后，
只对本 run 固定路径 receipt 将该字段校正为 true，再次回读逐字节验证。
该修复不改变 Release 结果包和任何科学数值。

## 验收

专用 profile/receipt 合成测试：7/7 PASS。
全公库 unittest：1390/1390 PASS（60.716s）。
synthetic Overnight BLACKBOX smoke：PASS。
修复前后 broker 与 test 文件 SHA256 无漂移。

下一步只能在本修复经审查合并后，使用同一冻结研究问题和标准
`workflow_dispatch` profile 重放。首次失败运行永久保留为工程证据，
不得删除、重写或把其数据暴露重新称为 fresh OOS。
经济干预及 signal/router/trade/paper/live/production authority 仍全部为 false。
