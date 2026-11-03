# Task03 实验协议与复现

## 冻结环境

分支 `task03/implementation`，起始 HEAD `5a95dd793f2f84d82a7431f9dbcc3142abcc482a`，Task02 基线 `4c3b67c0de70e090a4d0e96b558c2c91805ad60a`。开始时工作区干净；未切换/覆盖任何未提交文件，未改原模型、旧证据、旧 seal；未 commit/push/PR/merge。

Windows 10 19045，Intel64 Family 6 Model 141、12 逻辑 CPU、物理内存 16,893,382,656 bytes。Python 3.10.11，PuLP 3.3.2，CPLEX 22.1.1.0、CBC 2.10.3 实际可用；环境 smoke 原始结果在 evidence/environment.json。CPLEX threads=1、randomseed=11、parallel=1、MIP relative/absolute gap=0；CBC 使用原 Task02 路径。Python 子进程 PYTHONHASHSEED=11。

NumericPolicy 沿用 Task02：LP primal/dual=1e-8；PP 和分支整数=1e-7；列局部可行=1e-8；RC epsilon=1e-7；人工总和=1e-7；primal 读回=1e-6；界一致性=1e-5；全局绝对最优容差=1e-5，相对=1e-8。不同职责不混用，证书均保存完整策略。

## 运行顺序与预算

先运行 adapter 单测与独立小规模 Oracle，再复跑 Task02 双后端边界和历史组件回归，最后执行 n10/n20 3 秒 scout 与 n20/n30/n40 中等规模。最终补充数值契约和日志隔离后重新执行全量小规模检查，所有早期记录保留。

中等规模：两线，每线 n∈{20,30,40}；seed∈{11,21,31,41,51}。输入由原 generate_instances.generate 生成并原样保存，不改变生成规则、不使用构造 witness 给单个算法。每输入 V0/V1/V2/V3/Compact 共 5 臂，按输入交替正序/倒序；每臂独立新进程，串行运行。CPLEX import/初始化在预算前对全部方法一致预热，不把 native import 偶然成本归为算法差异。

名义总预算为 **5 秒**（短预算资源受控诊断）；V3 acquisition 从总预算扣除，最大占 20% 且不超过 2 秒。预算包含算法建模和求解，但实现使用软 deadline；完整证书序列化/写盘及不可中断段会超出 deadline。父进程另有 budget+20 秒 watchdog，仅停止自己的 worker；本轮没有 watchdog kill。记录包含实际 seconds、overrun、LB/UB/Gap、Windows 进程 peak working set、节点/PP/首解时间。由于实测超预算明显，**不能宣布严格公平总墙钟比较通过**。

Compact 的首解时间未从 native 日志解析，保留 null。B&P 首解时间为节点验证完成时刻（V3 为 acquisition 验证完成），不是求解器内部最初发现时刻。节点数仅统计已处理节点。RMP 的 LP 目标从不作为整数 LB。

所有 75 臂实际执行完返回 time_limit（含有效保留的活动节点），不是全局整数完成。未扩大预算到 120/300 秒，未运行 120/150 总任务实验。保留失败和诊断，不作超时删除筛选。

## 可复现入口

从仓库根目录 PowerShell，用已有 venv；输出目录必须尚不存在：

```powershell
$py = 'experiments/.venv/Scripts/python.exe'
$env:PYTHONPATH='code/dwcg;code'
& $py -m unittest test_task03 test_task03_faults -v
& $py experiments/task03_validation.py <new_validation_directory>
& $py experiments/task03_replay.py <validation_directory> <new_replay_directory>
& $py experiments/task03_interruptions.py <new_interruptions_directory>
& $py experiments/task03_benchmark.py <new_benchmark_directory> medium 5
& $py code/dwcg/task03.py code/milp/examples/two_lines.json --version V2 --solver cplex_py --time-limit 30 --output <new_result.json>
& $py docs/branch_and_price/task03/task03_verify.py --instance <instance.json> --result <result.json> --offline --output <new_verification.json>
```

Task02 原独立复核仍用 `docs/branch_and_price/run_validation.py --out <new_directory> --boundaries`。最终统计入口 `experiments/task03_report.py` 从本目录归档数据重新生成 RESULTS.md/JSON（只更新当前 Task03 派生报告，不改原始记录）。

source_snapshot/ 是中等规模执行时源码；最终交付哈希在 ARTIFACT_SHA256.json。二者存在后续数值检查、日志路径隔离与 CLI 差异，不能把前一快照的性能外推为最终代码已经全部性能复跑。所有证明仍属于记录浮点容差下的数值证明。
