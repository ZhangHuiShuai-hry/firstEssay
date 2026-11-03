# 时间、异常与组件剖析

新预算入口 `experiments/task03_1b_budget.py` 保持原 worker 进程级 deadline，所有导入、建模、验证、证书提交和父进程校验计费。worker 记录进程进入、algorithm 起点，首个已验证整数解由 API 相对时刻加进程偏移得到 E2E 时间；Compact 内部首解时刻仍未知，不填零。

operational_status 区分 timely_result、hard_stop、solver_error、missing_evidence、late_result。safe_summary_only 与可恢复搜索明确分开。未及时完成不采纳晚到最优标志；未提交的 SQLite 记录不可见。

accounting.json 先以 `final_admitted=false` 原子写入，标明 pending_final_admission。fsync/rename 后测量 accounting 完成时间，再写独立 admission 回执，包含 accounting SHA；只有该回执能决定正式采纳，不能把 accounting 候选标志当成证明。外层回执是观察日志，其自身发布仍非硬实时；Windows kill/wait 与 SQLite 恢复耗时保留 overrun，不声称绝对硬保证。

持久化组件已经显式互斥分解。固定同列池/同对偶微基准见 evidence/microbench/result.json：PP initialization 总量与 Python structure/native creation 子项，目标更新、native optimize、读回、额外验证 residual；RMP mirror、native初始化、追加、native solve、读回及证书核验。初始化子项不可与其总量重复相加。数值对照必须先通过，退化最优列可以不同。

**P0-4 仍 PARTIAL**：上述固定池微基准和生产原始 PP/RMP 记录已实现，但尚未在完整搜索中对所有列池管理、所有 PP 初始化/更新/读回及证书生成建立统一完整的互斥聚合。cProfile exclusive 可加，cumulative 不可加；不同搜索树的总时间不能归因于接口收益。

完整恢复、故障后恢复等价测试仍 NOT RUN；异常/强制停止与损坏证据测试通过只能证明 fail-closed，不能冒充恢复能力。
