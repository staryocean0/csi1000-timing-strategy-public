# R1剩余五段盲区：逐事件时钟核查

研究任务 #334，前置R1 #330，最终识别质量门 #321。本文冻结诊断口径，不是R2识别器，也不是已完成的市场归因结论。

## 研究为何来到这里

R1正式run `35112136370-1`、源码 `61e5dcdf143be4b9a5a7bb8bcae1c4a3f2a63af7` 已通过计算、独立验签和私库回存。非边界盲区从11,610根下降到414根，139/144个原盲区完全恢复，但剩余五段仍均属Q3/Q4，长度63、85、77、94、95根。414根包括322根原来就盲、92根R1新增的盲区。#321未通过，不能凭覆盖率达标引入1m。

前一轮准备包以合成路径复现了两种现象：反向极值太早产生，导致occurrence间隔持续小于4；超时检查先于当根价格，可能跳过同一根上的新极值或有效确认。它们只是待检查的问题，不能直接当作真实五段的原因。此次只观察冻结R1，不在观察过程中运行、修改或挑选R2。

## 两套时间不能混用

R1的过期条件是当根处理之前 `now-max(last_pivot_occurrence,candidate_occurrence)>48`。确认条件仍是 `counter_occurrence-candidate_occurrence>=4`，不是“已经等了四根”。每根K线记录处理前后mode、candidate、counter、last pivot、epoch及最近确认时点，并标出当根实际分支。

对reset当根另计算“这根价格如果先被检查，会不会更新candidate、更新counter、达到确认条件”。这些只是同一时点上的布尔条件，绝不回灌原状态，不模拟收益，也不声称某个修复已经成功。

## 五段与新增92根全部列账

每段以冻结R1盲区mask定位，并保存稳定ID、原振幅分位和长度。分开核算reset之前、reset当根、reset之后的发生时间覆盖；每一部分又分原有盲区与新增盲区。新增部分保留相对偏移段，完整绝对时间与OHLC仅留私库账本。

同时记录：候选点/反向点的真实发生位置与年龄、反向点距离、候选以来的实际分支次数、第一枚bootstrap确认与其左截断种子、第一枚非截断pivot、下一完整A波的开始和确认。这样能够区别reset前的未完成结构、reset后的重新启动损耗，以及R1与基准边界变化。

`EARLY_COUNTER_LOCK` 是“短occurrence间隔+长等待”的事件描述，不是仅凭不变量即可证明的普遍市场原因。内部涨跌次数也不等于已经验收的波数。最后必须回看完整OHLC，不能用计数替代形态判断。

## 独立核验范围

诊断数组回放与原R1全部pivots/resets/waves必须逐字段相同。另一个观察器继承原R1的run不改动，只在真正调用reset时记录状态；据此独立复核reset年龄和同根证据。盲区mask使用差分数组独立建立，核查全部五段和92根的数量、偏移、前后分区。

前缀核验包含全历史均匀截点和每次reset前一根及当根。固定市场运行必须精确复现70114根、2704波、5次reset、5个盲区、414/322/92的冻结总体。重跑同一诊断函数仅称可复现性，不将其冒充独立科学验证。

## 图形证据

重用未修改的 `wave_recognizer_r1_v1_visuals.py`，重建原20页：五个显著残余、十二个确定性恢复案例、首尾截断和最长波对照。所有原始OHLC蜡烛、当时允许显示的完整波与确认标记均保留。

为了完整读取已生成的SVG，在私库增加逐页字节数、SHA256和无损gzip-base64的JSONL读视图。这只是原SVG的传输封装，不是新图形或市场数据处理；读取后必须解压验签再人工观察。生成/机器校验图包不等于人工视觉通过，初始manual_acceptance仍为false。

## 标准执行和权限

固定profile `two-wave-r1-residual-clock-audit-v1`；唯一真实计算入口仍是 `public-compute.yml` 的 `workflow_dispatch`、`cloud-workspace-v1`。既有owner-only controller只为精确的新标题发起标准dispatch。本地仅公开源码与合成测试，不运行市场研究。

只用原5m、2015—2020、000852.SH、70114根、3351411字节、SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`。不读取1m、2021—2026，不换样本，不读PnL。

16个计算阶段文件及协议由manifest逐一固定。计算和只读验证各900秒、4CPU/12GiB、无网络无凭据。只有prepare/publish步骤映射受限私库Secret。raw event trace只进私有结果archive，Chat不直接写私库。

## 本次工程检查记录

首轮PR CI `35120863602` 在758项中仅stage-only导入检查失败：`python -I`排除了GitHub runner实际安装NumPy的用户级site-packages。其他诊断往返、真正R1对照和篡改反例通过。修复仅在子进程显式加入已加载NumPy/Pandas所属的site/dist-packages目录，仍排除原仓路径、保留固定stage源码闭包检查，没有跳过测试或改动计算隔离。

standard workflow与controller只新增本profile，测试删除这几个新增片段后应精确恢复原文件Git blob。最新head全量CI通过、审查合并后才创建唯一正式controller任务。真实run、私库receipt、逐例结论和人工图形意见在后续裁定中另行记录。

## 下一道门

先完成五段及92根真实归因和视觉核查，然后才能独立预注册R2。既不把合成反例当市场归因，也不把这次诊断通过当#321识别质量通过。所有signal/detector-repair/router/trade/production authority保持false。
