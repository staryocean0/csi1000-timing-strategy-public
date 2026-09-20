# Model B / #635：概率校准组件实现与合成验收

日期：2026-09-20。
状态：`CALIBRATION_COMPONENT_TESTED__FULL_STUDY_PENDING`。
上游：已合并 PR #636，公库基线 `201b776cdeb28913b7ec27c7b6cd57b5b2557d0a`。
预注册不变：`TWO_WAVE_MODEL_B_P128_STATE_EXIT_PREREG_20260920.*`。

## 本次实际增加

`executor/two_wave_model_b_p128_calibration_v1.py` 只提供不读市场文件的概率组件：
P128 当时可知 context、固定12/16列 A/B design、固定 ridge Newton 校准、
完全相同训练行的成对拟合、UNRESOLVED 时精确 B=A 回退、逐行概率损失，
以及 label-free reference 与已成熟 supervised training 的独立选择。

label-free CDF 保留所有 prior-year eligible decision rows；训练选择先检验
`known_index+8 < cutoff` 和 context-resolved，再按已选行键读取标签值。
它不会因尚未成熟的标签被污染而改变已完成的 prior fit。

这是源码组件，不是完整研究 producer、独立研究 verifier 或标准执行 profile。
没有读取冻结市场数据，没有产生 #635 市场结果或科学裁决。
#624 的代码、score、target、年龄档、数据和负结论均未修改。

## 真实测试收据

新增合成 unittest：15/15 PASS（0.090s）。
全仓 unittest：1366/1366 PASS（60.516s，exit=0）。
既有 P128 context 与已合并 prereg 的 pytest：12/12 PASS（0.69s）。
测试后复核7个源码/合同哈希，全部与运行前相同。

合成检查包括完整窗口/flat/非法 context、prefix 与未来扰动、嵌套设计、
固定优化器收敛与不收敛处理、缺失精确回退、训练支持不足、严格跨年标签成熟、
污染未成熟标签不改变 fit、未来样本不改变既有 CDF/score。
另用 SciPy BFGS 独立计算合成目标作数值交叉检查；这不是全研究独立 verifier。

源码 SHA256：
- 校准组件：`3f48d4f052c2a14e4755e33683cc5ddf84ce42462f67312c948023f9fa90b667`
- 新增测试：`53e0d1c27fda849a7cd462323a8c56583fe63dd3731d7b823836491f305f6172`
- 冻结 prereg JSON：`31784bcc4d4613347b1cda2e68f332e6d02703b9fcec3f07fc92834df875f508`

授权 Debian 的收据目录：
`/home/starryocean/桌面/量化/csi1000-research-receipts/model-b-635-takeover-20260920-0626/`
包含 calibration_tests_initial.log、full_unittest.log、prereg_context_pytest.log、
source_hashes_before.txt，以及历史 v2 的独立文件/运行回读 JSON。

## 承接核验与未完成范围

历史 v2 已由先前 #633/#634 两阶段完成。本次独立回读确认 private main
`2815f50b5a1b2925f0e0118b0af0d578605ee882` 仅修改历史文档；两库 blob 都是
`b683b2f70758bb4f22236009f15306223c48c588`，29,544 bytes，内容逐字节一致。
本次没有重放同步请求，也没有修改 private main 或其他共享工作树。

下一实际接口是完整 decision stream：预测不依赖未来标签；仅在评价层附加
#624 的 +16 完整支撑，然后逐行核对原29713行基线身份。接着完成 coverage、
年度 fit integration、成对 block bootstrap、固定判定门和完整新链 prefix 验收。
独立 verifier、固定 source manifest/profile、标准 governed run、私库回存回读
和最终 exact result 都仍未完成，不能以本次合成 PASS 替代。

## 工具返回与证据边界

本次一次额外测试追加和一次批量历史材料只读请求被平台拦截，返回：
“因 OpenAI 无法确定请求的安全状态，已拦截此工具调用。”未提供更具体原因。
自查范围是当前公库源码/合成测试与只读历史材料；没有发现可证实的具体原因。
被拦截的追加没有落盘，不计入15项测试；被拦截的材料读取不声称完成。
这些动作未换接口、编码或路径重试。原因记录为 unknown，而不是权限缺失或关键词归因。

工程：仅本组件合成验收通过，完整研究仍在实现阶段。
信息门：未评价。经济干预：未验证。
signal/router/trade/paper/live/production authority：全部 false。
