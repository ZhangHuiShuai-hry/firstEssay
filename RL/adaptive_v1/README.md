# 第二阶段：候选找列＋原价认证回退

核心入口online.py，策略exact、short_raw、fixed、adaptive；算法/数学协议见PROTOCOL.md、DESIGN.md。RESULTS.md与SUMMARY.md在完整运行后生成。证据保存在evidence/，旧目录不修改。

复现步骤：

1. `python RL/adaptive_v1/batch.py --stage small`：4小例×4策略；输出新目录，现有目录存在时拒绝覆盖。
2. `python RL/adaptive_v1/test_safety.py`：已保存小例的Oracle与故障检查。
3. `python RL/adaptive_v1/batch.py --stage medium`：3开发中例×4策略，每个60秒软算法预算。
4. `python RL/adaptive_v1/verify_bundle.py <结果目录> --output <新文件> [--no-enumeration]`：严格持久化证书核验；中例指定no-enumeration，小例完整枚举。
5. `python RL/adaptive_v1/test_injected.py`：测试进程注入候选未证状态，验证仍可补列并由后续认证闭合。仅模拟测试，不是实际超时性能记录。
6. `python RL/adaptive_v1/analyze.py`、`profile.py`：输出同输入/同源码校验、结果表及非重叠原生耗时。`seal.py`封存，`seal.py --check`复核。

使用仓库虚拟环境experiments/.venv/Scripts/python.exe；CPLEX路径/依赖沿用solver_backend，生产模型不改。所有正式结果使用固定源码；需要复验时请复制代码到新的实验目录并改输出路径，保持原始证据与哈希不变。

新证书candidate-certified-1区分候选与认证，旧根CG、reuse_v1入口保持可用。严格结果复核优先使用verify_bundle.py；audit.py只负责数学重放，不单独代表源文件完整性或全部原生状态契约。
