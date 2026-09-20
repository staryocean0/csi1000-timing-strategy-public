# Model B / #635：执行前审阅与未闭合项

日期：2026-09-20。状态：`EXECUTION_HOLD__QUALIFICATION_NOT_COMPLETE`。
审阅对象：PR #638 / `89217d4811c52e69505475c2d176cd1f3d8ecc2f`。
此前 PR #637 的校准组件已合入；其15项合成检查、1366项全仓回归和公库 CI
均通过，但这些结果不能替代后来 #638 完整研究链的验收。

本轮没有读取冻结市场样本来计算 Model B outcome，没有调度该市场 profile，
也没有改变目标、representation、模型家族、阈值或原 #624 判定。
以下是执行前的合成反例和源码审阅，不是 Model B 的信息门负结论。

## 已复现的验收缺口

1. #638 producer/verifier 的 snapshot 只含预测行。早期只有 decision rows
   时，将 state_age 从5改成99，原版仍返回 prefix-equal=true。
2. 删除一个已经产生预测的年度 fit，原版仍返回 prefix-equal=true。
3. 更换 training row identity、保持数量及系数不变，原版仍返回 true。
4. 训练样本缺失9个方向×年龄格子时，原版 producer/verifier 仍调用优化器，
   而不是在拟合前执行固定的支持门。

源码审阅还发现：verifier 未核验 exact 中的 authority、coverage、
relation_support、meta 等全部声明；账本检查遗漏 context_g 等字段。
完整 label-free coverage 预检、显式支持不足结果及其独立验收也仍需完成。

## 已成功写入的局部修复

producer 已纳入完整五态/carrier 过程及早期 decision 的状态、年龄、特征、
context 值/缺失原因；预测行键也要求完全相同，不再只比较交集。
训练 coverage 和 direction×age cell 支持检查已移到对应优化器调用前；
只有 resolved 且严格成熟的训练行读取标签。label-free CDF 未改变。
新增 reference/training/label 行身份记录，最大标签时点按实际 fit rows 记录。

合成反例确认：局部 producer 已拒绝早期 state_age 改动；支持不足时不再
调用优化器，而是抛出明确的 InsufficientSupportError。
这尚不等于完整“支持不足结果”已经接通 runner/verifier。

## 必须保持未闭合

新增6个验收回归中，当前1项通过、5项失败，失败未设 expectedFailure 或跳过。
缺失年度 fit、训练行身份替换的拒绝逻辑尚未写入；verifier 尚未同步本轮
完整 decision 检查及支持门。source manifest 保留已合并版本，尚未刷新。
因此该补丁只可作为 draft，不得据此调度受控市场计算或关闭 #635。

第三次平台拦截发生在追加 producer 的拟合身份检查及回放计数时，返回：
“因 OpenAI 无法确定请求的安全状态，已拦截此工具调用。”未提供具体原因。
该段没有写入，未更换接口、编码或路径重试。此前两次拦截见 #637 组件记录。
随后仅继续已允许的合成诊断、失败回归与进度留存，没有把拦截归因为关键词或权限。

这些反例证明验收器可能漏检，不证明已有市场结果发生了未来信息泄漏。
信息门、经济干预、更高阶段权限均未通过本轮获得任何授权。

## 完整补丁回归收据

本工作树实际运行全仓 unittest：1384 项，59.318s，exit=1；
5 项失败正是未闭合的新增验收反例，另有2项 profile 测试报错。
两项报错均为 `issue635_public_source_identity_failed`：producer 已作局部修复，
但受控 source manifest 仍固定在已合并版本。源码身份门因此拒绝当前补丁。
不通过刷新清单来掩盖尚未完成的 verifier/验收修复。

运行后核对7项当前补丁、测试、旧模块及 prereg 哈希，与运行前全部相同。
此前 PR #637 的1366/1366 PASS 不替代本工作树的1384项失败收据。

授权 Debian 收据目录：
`/home/starryocean/桌面/量化/csi1000-research-receipts/model-b-635-takeover-20260920-0626/`
主要文件：`PRE_EXECUTION_DIAGNOSTICS.json`、`acceptance_regressions.log`、
`repair_full_unittest.log`、`repair_hashes_before.txt`。

该记录和局部补丁只进入独立 draft review；不合入默认分支，不改变已合并
profile 的源码身份，不调度市场运行，不关闭 #635。
