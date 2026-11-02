# Task02 推送后审计附录（2026-11-02）

- **审计对象**：GitHub 仓库 `ZzzHry/firstEssay` 的 `main@4c3b67c0de70e090a4d0e96b558c2c91805ad60a`，父提交为 `70d5bca0c3635691dcaff9377ee4abf44576e35b`。
- **审计方式**：通过 GitHub 连接直接审阅 `code/dwcg/node_state.py`、`node_pricing.py`、`node_master.py`、`bp_solution.py`、`branch_price.py`、`docs/branch_and_price/independent_bp_verify.py`、研究报告及已提交的部分逐节点证据；核对已保存的统计汇总和离线重放报告。**未在新机器独立执行所有求解/测试，也未逐字节验算 6619 个证据文件**。
- **结论**：**有限范围审计通过，可以据此开展 Task03**。当前 B&P 的原 `x` 0/1 二分、定价固定、广义弹性 Phase I、对偶修复节点 UB、整数 witness 与 DFS 活动节点保留机制，从源码结构和样例证据看相互一致。在小规模已提交验证范围内，未发现足以阻止下一阶段的证据冲突；这**不等于**形式化、精确有理数证明或大规模效率认证。
- **已提交证据摘要**：`BP_VALIDATION_REPORT.md` 声称 29 个输入×双后端共 58 次完整搜索（48 最优、10 整数不可行）；`evidence/validation_final/summary.json` 和 `additional/summary.json` 与此计数吻合。`evidence/ACCEPTANCE_TOTALS.json` 记录 22 个独立节点、6 个中断/精度测试、10 类假证书拒绝。代表性逐节点 `two_lines_cplex_py` 根 LP=27、全局整数=24；`generator_n6_L1_s13_cplex_py` 根 LP=59.38、整数=56.63；`lp_yes_ip_no_cplex_py` 根 LP=4、两个叶 Phase I 修复 UB=-0.5 后证整数不可行。
- **证书验证**：独立枚举器来自 `docs/research_audit/independent_validation.py`，不依赖生产定价器/生产列系数组装；但独立 Full-LP/IP 仍借用同一 PuLP 求解器适配，因此是**建模/定价算术上的独立交叉验证**，不是完全独立求解器软件或形式证明。现有独立 `certificate_replay/summary.json` 报告 64 树、22 节点离线重放成功、10 类伪造拒绝；本附录将其作为已有证据，不声称审计者重新运行。
- **版本与历史字段解释**：`TASK02_SUMMARY.md` 里的 `HEAD=70d5bca`，以及 `SEAL_RECEIPT.json` 里的 `task02_commit_created=false`、`task02_pushed=false`，均为**封存执行时刻**的真实历史状态；后来 Task02 作为提交 `4c3b67c` 推送到 GitHub，二者不矛盾。不要修改旧封存文件来追认今天的状态。
- **尚未证明**：未进行 120/150 总任务 Task02 B&P 性能试验；未实现跨节点模型复用、截断 PP best-bound 驱动完整证书、RL；未提供可验证的精确有理数证书。GitHub 提交未见关联的 CI status checks。Task03 应保持上述范围界限。
- **下一步**：执行 `docs/branch_and_price/TASK03.md` 的可切换持久 PP、增量节点 RMP、受检验整数 LB、安全界与公平规模实验。保留 Task02 原始源码与证据，不覆盖。
