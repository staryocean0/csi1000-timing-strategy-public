# Two-Wave 历史沿革 v2：两阶段同步验收

日期：2026-09-20。状态：`COMPLETED_AND_READ_BACK`。

唯一同步目标：`docs/research/TWO_WAVE_STRATEGY_EVOLUTION_HISTORY_20260920.md`。
这是已有文件的 modified 同步，仅补齐 #624 最终验收与第 17 节；没有重跑 #624，没有修改私库总入口或研究权限。

## 实际闭环

- public stage PR #633；测试 head `07503d0fb822300ebc4fa6d763b865e2c6552149`。
- stage public merge `471d742d25ae9ecd4609730d3c16fc9c4e6e1b8c`；governance run `35492996903` success。
- private base `22ab2e181407fb1d0a9a71e61d880819fe1baec8`。
- staged head `2815f50b5a1b2925f0e0118b0af0d578605ee882`。
- stage 回读：ahead=1、behind=0、merge-base=base，仅一个 modified 文件，公私字节相同，main 在 stage 时未改变。
- 独立 public merge-phase PR #634；仅 request.phase 由 stage 改为 merge。
- merge public commit `6e0ff1c9f9b05bf6b023840934f6846c14c85f1d`；governance run `35493236442` success。
- 既有 workflow 以 `force=false` 推进 private main；未直接操作 private ref。
- 最终 private main 回读为 `2815f50b5a1b2925f0e0118b0af0d578605ee882`。

## 内容身份

- 旧 blob：`b22930c3462f3fdc479f97db7a0f44c684bdc228`。
- 新 blob：`b683b2f70758bb4f22236009f15306223c48c588`。
- bytes：29,544。
- SHA256：`932fd8625b9d046604f5b6c745ae7bdf1f58a754d703f56ad021e8498d7f1eaf`。
- 私库 main 文件、blob 和完整字节均再次核验；第 17 节存在。

## 本次测试，不继承旧回归收据

保存的三文件 v2 补丁：synchronizer self-test PASS，专项 unittest 3/3 PASS，全仓 unittest 1345/1345 PASS（59.371 秒）；测试前后文件 SHA256 一致。
PR #633 远端 public-tests run `35492816354` / job `106030551800` success。

独立 merge-phase 补丁：self-test PASS，全仓 unittest 1345/1345 PASS（59.081 秒）。
PR #634 只改治理 request，不匹配 public-tests 的 paths filter，因此没有该 PR 的远端 regression run；不能写成远端 CI 通过。受控 merge workflow 自身成功。

Debian 持久收据目录：`/home/starryocean/桌面/量化/csi1000-research-receipts/history-v2-20260920`。
保留测试日志及哈希、stage_readback.json、final_readback.json、merge_tests.json。
一次本地 GitHub 读取发生 TLS timeout，后续有界重试成功；不影响已有 stage 或 main 内容。一次批量读取请求被平台拦截、原因 unknown；未执行该批量请求，改为必要的单项核验，没有扩大权限。

## 边界

这关闭的是历史同步工程尾项，不改变 #624 的 NOT_SUPPORTED，不授权交易。
私库 CHAT_START/CLOUD_CURRENT 仍描述旧 Layer2 研究锚点；本次单文件同步未擅自重写它们。Two-Wave 当前用户授权线程的研究语义以已合并专属材料及后续独立预注册为依据，不宣称私库根控制面已整体更新。
