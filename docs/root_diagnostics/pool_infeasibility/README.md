# 列池整数不可行解释实验

入口：`code/dwcg/diagnose_pool.py`。默认读取已封存40任务无Compact初始解的证书，检查Phase II第25轮434条列。可在IDE用`experiments/.venv/Scripts/python.exe`直接运行；默认只打印，不写文件。它不重新跑CG、不修改列、不修改原模型。

```powershell
experiments/.venv/Scripts/python.exe code/dwcg/diagnose_pool.py
experiments/.venv/Scripts/python.exe code/dwcg/diagnose_pool.py --iteration 10 --output <新的目录>
experiments/.venv/Scripts/python.exe code/dwcg/diagnose_pool.py --iteration 0
```

`--iteration 0`检查最后保存的Phase II列池；正整数检查对应迭代**求解RMP时**的池，不含该轮结束才加入的列。`--certificate`可选其他根诊断证书；实例文件须在证书旁或父目录，分支节点明确拒绝，以免忽略分支限制。输出目录存在时拒绝覆盖。

方法：先求原受限整数主问题；随后保持每站恰选一条局部可行列为硬约束，对任务唯一性/必做、前缀AND、共享资源、回收行加弹性变量，最大化负的人工变量和。打印每站列号、任务模式、节拍/疲劳、人机配置、必做任务执行次数及违约行的LHS/RHS和违约量。违约量用所选列的原始行向量重新计算，与求解器目标交叉检查。

这不是从不可行求解器状态读取无效变量。打印方案来自另一个可行的弹性整数模型，是一个解释方案；目标没有经济利润项。诊断最优有多解，所违反的具体行不是唯一不可行核心，单位不同的违约量按原单位等权相加。超时若有经过检查的分配可以打印，但`minimum_violation_proven=false`；没有incumbent则不打印分配。

## 已实际运行的CPLEX结果

`round25_final/allocation.txt`和`diagnosis.json`：原受限IP证明不可行；弹性IP证明最优，最小总违约2。

- 列池对8个必做任务全部有覆盖，不存在某个必做任务完全没有任何候选列。
- 选出的解释方案中，L1第7站执行17却没有执行前驱15，违反15→17的末前缀行，违约1。
- L2任务23同时出现在第1站和第7站，违反必做任务恰好执行一次，违约1。
- 其余主问题约束满足；每站局部时间、疲劳、模式与配置约束满足。

因此，对于这一池，问题是**列的组合无法同时满足全部全局行**。覆盖每个任务只是必要条件，不保证能选出无重复且遵守优先关系的整数组合。

`round25_only_precedence_relaxed`：通过以下命令保持任务、资源、回收行全部为硬约束，仅允许优先关系违约；证明最小违约3：15→17、25→26、39→40的末前缀各违约1。

```powershell
experiments/.venv/Scripts/python.exe code/dwcg/diagnose_pool.py --hard-family task --hard-family human --hard-family robot --hard-family recovery
```

这说明本池可找到满足全部任务/资源/回收约束的整数配置，但仍需违反优先关系。它不是删优先约束的建议，也没有证明上述三条边组成唯一冲突核心。不能将第25轮池的结论外推到完整列域或原问题整数不可行。

`round25`是首次诊断原始输出，`round25_final`是增加必做任务次数打印和输入哈希后的输出，两者均保留。

CBC交叉尝试：PARTIAL/未证明。名义30秒软预算后，其弹性整数模型原生进程仍未返回（非硬实时）；确认CBC子进程及其Python父进程属于本次运行后，停止该CBC子进程，Python报PulpSolverError。没有取得可采纳的CBC弹性最优解，`round25_cbc/error.json`保存中断信息，不宣称CBC验证通过。没有调整求解精度或删除这次失败。脚本软预算不保证native API硬停止。

11项测试PASS（`tests.txt`）：5项新诊断测试覆盖缺失必做任务、任务重复、优先关系、资源、回收、可行池、硬约束冲突和池不变性；6项既有根诊断回归继续通过。没有重跑整棵B&P性能实验。
