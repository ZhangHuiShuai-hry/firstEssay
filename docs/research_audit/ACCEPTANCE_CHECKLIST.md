# 验收清单

日期：2026-11-02。PASS指已完成指定理论或实际数值验证，不意味着任意规模/病态输入已获形式化计算机证明。

| 阶段 | 项目 | 状态 | 证据 |
|---|---|---|---|
| 0 | 提交、分支、原始工作区修改检查 | PASS | baseline.json；初始无用户修改 |
| 0 | 代码和依赖版本 | PASS | PROJECT_BASELINE；requirements-lock |
| 0 | CBC/CPLEX环境及实际求解 | PASS | environment.json |
| 0 | SHA-256清单 | PASS | baseline.json、HASHES_FINAL.tsv、EVIDENCE_HASHES.tsv |
| 0 | 现有功能、版本关系、缺失功能 | PASS | PROJECT_BASELINE、IMPLEMENTATION_AUDIT |
| 0 | 原始实验保护 | PASS | 历史目录只读盘点；未删除/覆盖 |
| 1数学 | 紧凑MILP和完整列模型 | PASS | MATHEMATICAL_AUDIT |
| 1数学 | 双向整数等价证明，包括空站/配置 | PASS | MATHEMATICAL_AUDIT第5节 |
| 1数学 | LP松弛包含关系 | PASS | 证明及参考例严格差异 |
| 1数学 | RMP对偶及全部reduced-cost项 | PASS | CG_DERIVATION |
| 1数学 | 两阶段、完整定价终止 | PASS | 推导和实际状态/边界测试 |
| 1数学 | 定价Best Bound上界公式及条件 | PASS | 对偶修复定理；任意放松上界独立测试 |
| 1程序 | 完整列独立枚举 | PASS | 28实例×3实现/后端组合 |
| 1程序 | 四模型及CG-LP交叉验证 | PASS | 84次验收运行 |
| 1程序 | 两阶段PP独立枚举比较 | PASS | 360次任意对偶定价，另有CG调用 |
| 1程序 | 双向整数映射和LP投影 | PASS | 独立primal检查及代回紧凑约束 |
| 1程序 | 对偶检验数和完整证书重放 | PASS | 374轮；84份离线证书全部通过；6种篡改被拒绝 |
| 1程序 | CPLEX/CBC比较 | PASS | 相同28输入状态和目标一致 |
| 1程序 | 相关回归 | PASS | CBC45、CPLEX45、实验32 |
| 1程序 | 失败项解释及保留 | PASS | VALIDATION_REPORT；修复前与测试适配器失败目录 |
| 边界 | 以截断PP Best Bound继续CG/签发本轮新上界 | NOT IMPLEMENTED | 当前算法仅接受已证最优定价，此扩展不属现有能力 |
| 边界 | 机器严格有理/区间最优性证书 | NOT IMPLEMENTED | 当前为明确浮点容差下证明 |
| 边界 | 全部历史大规模实验重跑 | NOT RUN | 不运行120/150任务；历史文件完整性另行验证 |
| 边界 | 旧无hash快照的历史密码学完整性 | PARTIAL | 20261030_112527只有用途说明 |
| 边界 | Branch-and-Price整数全局算法 | NOT IMPLEMENTED | Phase2待完成；本次不实现 |

本次Phase0/1范围内验收完成。上述边界不应被统计成已实现能力；进入Phase2须遵守TASK01_SUMMARY中的节点级验收条件。
