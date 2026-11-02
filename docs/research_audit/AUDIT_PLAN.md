# Task 01 审计计划

日期：2026-11-02（Asia/Shanghai）。范围仅 Phase 0/1，不实现 Branch-and-Price。

1. 只读盘点已完成：读取两份 LaTeX、紧凑模型、列定义、RMP、PP、CG、验证器、原生适配器及实验调用链；读取 Git 状态。初始工作区干净。
2. 固化提交、全部受版本管理文件的 SHA-256、依赖、原有忽略目录和历史材料的完整性。普通 `rg --files` 忽略 runs/snapshots，必须另行盘点。
3. 重建模型并证明双向整数映射及 LP 包含关系；重新推导对偶、前缀后缀贡献、两阶段及上界。
4. 新建独立局部枚举器、完整主问题及可行性检查器，不调用生产 make_column/coefficients/build_master 作为独立 oracle。用现有生产函数作为被测对象。
5. 先运行现有回归和独立测试；保存输入、配置、事件、原生日志、证书和结果。规模最多每线 6 任务（总任务最多 10），不运行历史大规模实验。
6. 已列入待证假设：通用求解器 Best Bound 可能遗漏 PuLP 目标常数；证书缺少状态和部分失败记录；旧 verify_checked 的通过语义弱于现 verify。先重现再修复。
7. 仅修复确认的错误，保留旧结果和数学假设，回归后生成七份中文报告。所有未验证项明确标为 PARTIAL/FAIL/NOT RUN。

稳定参照入口：`code/milp/model.py`、`code/dwcg/solve.py --verify`。增量 RMP 和持久化 PP 由实验运行器注入，同一套 CG 主循环；版本号必须连同运行器解释。
