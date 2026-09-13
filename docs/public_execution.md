# 公库计算、私库保存与代码回合

Chat/云端控制器负责研究设计和调度；私库固定源码、输入和验收；公库标准runner执行批准profile；broker回存私库分支和私有Release。公库自己的GITHUB_TOKEN仅contents:read，不能据此推断私库权限。

## 通用代码修改后合入私库

在公库独立开发分支修改可公开的通用工具，跑合成测试，审查diff，再合入公库活动分支；记录确切source commit。随后在私库独立分支按文件清单导入，核对双方同名文件差异后逐段合并，保留旧冻结源码。私有策略改动直接在私库完成；不得为“先公后私”公开私密策略。最终以私库PR或明确回执接受，不覆盖全部runtime。

## 已登记profile

- runtime-smoke：仅测试公开运行环境、断网和无凭据，不取私有数据。
- handoff-verify-v1：固定private commit、五个私有验签源文件与一个固定Release asset；在无网络、只读输入、4CPU/12GiB容器核验2813个包成员，由另一个只读验证步骤复核。它不训练、不重跑策略、不读取未来收益选参。

初始交接验签通过后，每个新的策略研究另行固定源码、数据范围、命令、资源和验收再注册profile；不能把任意shell或任意private ref变成workflow输入。首次上传、计算通道、独立验签与策略科学结果是四个独立状态。

公开工作流只workflow_dispatch，固定cloud-workspace-v1，固定ubuntu-24.04，无push/PR自动私密执行、无artifact/cache。取数和回存才映射受限Secret，计算/清理都不携带。收据及日志回存私库runs/public-research/<run>-<attempt>和public-research-run-<run>-<attempt>。

费用核对：GitHub官方说明公库标准hosted runner免费，私库含一定免费额度后计费；larger runner并非免费。本设计不启用私库Actions、不启用larger runner。依据：https://docs.github.com/en/actions/concepts/billing-and-usage 。
