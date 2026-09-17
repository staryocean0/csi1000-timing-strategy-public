# #352 S1 DataHub 1m/5m offset 来源与构建检查点

日期：2026-09-17。状态：**源码/合同来源已绑定；2015—2020 六份开发文件的二进制资格和共同支持尚未正式运行。**

## 已定位到真实生成链，而不是继续猜测

本地只读检查定位到 `unified_datahub` 的正式 V3 导出：

- export commit：`d31b140e35132911aa6ab164deaa9afcbb02b0ff`（2026-08-24，`feat: add T0 unified index kline V3`）；
- export id：`factorlab_unified_index_kline_v3_20260824`；
- schema：`factorlab_unified_index_kline.v3`；
- 证据manifest SHA256：`c46f2da6c3df016ca054e183e37267dc472097450fcdd6644c22aa0084c15749`；
- 固定 1m parent：`bars_cn_index_1m_raw_canonical_market_index_baidu_3s_20000714_20260821_factorlab_unified_missing_day_repaired_v8_20260824`。

这里的 DataHub 只作为数据来源/构建证据，不成为中证1000项目的current authority。

## 5m 五相位的真实规则

V3 明确增加 `1m_official` 和 `5m_offset_0..4`：

- offset0：官方 `session_end_label_v2`；正常日48根；
- offset1..4：`session_wall_clock`；正常日各46根；
- 上午和下午分别分桶，午休不跨段；
- 偏移网格之前的头部分钟不进任何完整桶；
- 不完整尾桶默认丢弃；
- 因此 shifted 5m 每个正常交易日天然比 offset0 少两根完整bar。

所以开发数据中 offset0 的70,114根与 offset1..4 的约67,192根之间的差异，**方向和数量级本来就由合同决定**；不能把它直接解释成“缺了约2922根数据”。
后续正式run仍需按真实交易日和短日逐项核对精确数量。

聚合本身是标准OHLCV摘要：第一条open、区间high最大、low最小、最后close，量额求和。它不是低通滤波。

## 1m 缺失分钟与5m的关系

V3 的 `1m_official` 输出另有因果稠密化：非短日最多缺5分钟时，用此前已观测close平铺，明确 `future_value_fill=false`；缺失严重的日期进入排除清单。
中证1000在完整V3证据里的排除日为：

- 2016-01-04；
- 2016-01-07；
- 2017-08-24；
- 2020-04-20。

重要区别：**5m产品通过原始固定1m query路径直接生成；后来给 `1m_official` 输出做的flat-fill不会反灌到5m构造。**
V3 finalizer 只是把不合格日期的排除范围传播到1m和所有5m offset研究视图。

因此以后用开发仓的 `1m_official` 重建5m时，不能不加区分地要求每根逐字节相同：
必须先根据真实字段识别flat-fill、eligible和excluded日期，再决定哪些物理区间具有“可精确重建”的资格。

## 仍未证明的事情

外部 `factorlab-two-wave-strategy-lab@152ae1ef...` README声明2015—2020文件来自冻结DataHub产品并未本地重采样，但本检查点还没有正式读取六个Parquet去核对：

- 实际bytes/hash/schema；
- timestamp和上海交易日对应；
- `causal_flat_fill` / eligibility字段是否完整保留；
- 每个5m bar的实际分钟构件；
- 共同物理时间支持；
- 2015—2020截断是否严格等价于V3对应切片。

这些属于 #352 下一步的固定标准 `workflow_dispatch` 审计，不在本地直接跑真实行情。

## 下一门

正式S1必须同时保留每套offset自己的总分母和共同支持分母；按时间而不是行号匹配，并报告边界/短日/缺分钟造成的attrition。
只有构建与共同支持通过后，#353 才能在真实数据上评价本尺度主导性、offset敏感性与参考切分。
