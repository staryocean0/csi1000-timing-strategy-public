# 5分钟识别器修复 R1：推进感知的失效时钟

研究 #330；总验收门 #321；前置盲区定位 #324（正式run 35104182684-1）。本轮只评估一个候选，不改4/48数值，不依赖C2/C3行情状态，不引入1分钟，不看收益。

## 数学变化
旧规则在处理当根bar之前检查 now-last_confirmed_pivot_occurrence>48，就清空未完成结构。R1在相同处理位置检查 now-max(last_confirmed_pivot_occurrence,live_candidate_occurrence)>48。候选极值不断推进时延续结构；counter本身不刷新时钟。反向成熟仍是候选与反向极值发生位置间隔至少4根。close选点和wick几何、bootstrap左截断均不变，绝不强行造波。

## 冻结评价
沿用#321与#330：非边界盲区<=2%；Q3/Q4残留<=5段且<=0.25%bars；残留至少90%为Q1；高振幅残留不得长于1.5T0。波数<=1.25倍基准、波长和振幅/通道高度中位数>=0.75倍、低幅波占比最多增加5个百分点、确认延迟中位数最多增加4根、p90最多增加8根。
T0恢复为前置诊断使用的2015—2017基准完整波时长中位数向上取整（真实基准预期21），不按候选周期重新标尺。幅度分位以冻结基准完整波全集为参照；它仅用于事后质量评价，不进入实时识别器。
无剩余非边界盲区时，残留Q1条件按空集通过，但明确报告首尾排除数量/长度、全样本盲区、每年差异；不把整个行情都藏进dataset edge。

## 独立核验和证据
单独数组状态机重放R1，不调用候选engine；逐项核对pivot/reset、原始OHLC锚点及完整波。原4/48单独重放核对baseline。独立差分计数覆盖mask及数值门，并做8个前缀的完整wave/pivot/reset一致性检查。全报告再生成仅标记可复现性，不代替独立核对。
完整OHLC私有图包包含：按稳定hash选择12个原盲区、全部残留Q3/Q4、最多各6个Q1/Q2残留、首尾区间及最长波控制；每页最多240根，不抽样删K线。基准虚线、R1实线、确认竖线分开。图形为明确标注的历史结构审查，不将发生坐标回填为实时可知标签。
自动核验检查每根蜡烛与图形内容；人工视觉验收独立。数值全过也不自动设置geometry_evidence=true或允许上传1m。

## 执行边界
新profile two-wave-recognizer-r1-progress-reset-v1，只走public-compute.yml/真实workflow_dispatch/cloud-workspace-v1；controller精确标题匹配。固定2015—2020、000852.SH、70114根5m，SHA256 bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48。
11个固定stage源文件包含协议与所有import依赖。计算与核验各900秒，4CPU/12GiB/无网络/无凭据。运行结束cleanup后由原窄范围broker写专用私库run分支/Release；report和visual index、最多24张SVG作为私库回读视图，完整图包只保存在私有结果archive。Chat不直接写私库，不改其他研究源码。
new_training=false、outcomes_used=false；signal/detector_repair/router/trade/production均保持false。数据属于已消费Development，不称fresh OOS。

## 验收状态
本说明写于真实R1结果读取前。此前本地短序列cutoff边界错误留作工程记录；本次改为0..n-1的合法8点取样并独立重放。通过代码/CI后才正式调度。正式回执、数值裁决和人工图形裁决另追加，失败不覆盖，不在R1上事后改参数救结果。
