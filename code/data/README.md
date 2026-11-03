# 共享算例与直接运行方法

两个入口默认读取 `tasks005_lines02_each03-02.json`，均可在 IDE 中直接点击运行，无需设置工作目录或命令行参数。请选择已有 `experiments/.venv/Scripts/python.exe`，或其他安装了 PuLP、CPLEX Python API且具有许可证的解释器。CPLEX 的自动定位由项目 `code/solver_backend.py` 管理；其他机器可安装可正常 `import cplex` 的版本。

|文件|总任务数|线数|每线任务数|来源与已知小规模整数最优|
|---|---:|---:|---|---|
|tasks003_lines01_each03.json|3|1|3|原single_line，21|
|tasks005_lines02_each03-02.json|5|2|3、2|原two_lines，24；Full-DW-LP为27|
|tasks006_lines01_each06_seed13.json|6|1|6|原generator_n6_L1_s13，56.63；Full-DW-LP为59.38|
|tasks020_lines02_each10_seed11.json|20|2|10、10|已有合成scout输入；未在此声明整数最优|
|tasks040_lines02_each20_seed11.json|40|2|20、20|已有n20每线pilot输入；未证明整数最优|

`tasksNNN` 明确表示**所有线合计**任务数，`each` 表示每线数量；不是把每线20任务称为总任务20。数据按原始字节复制，未更改模型、生成规则或历史输入。MANIFEST.json 保存来源路径、规模和 SHA-256；没有提供生成器构造见证给某一种方法。

## 默认策略和参数

- `code/milp/cplex_solver.py`：原始紧凑MILP交给CPLEX，单线程、seed11、相对MIP gap=0、软时限120秒。
- `code/dwcg/dwcg_solver.py`：默认 DW+精确列生成+Branch-and-Price，V2持久化PP/增量RMP、单线程seed11，节点上限10000，每阶段CG上限1000，软时限120秒；沿用审计NumericPolicy。`--strategy cg` 则仅求根Full-DW-LP及受限列池IP，不将其误标为原IP整数全局最优。
- IDE 调参：编辑脚本顶部中文注释下的默认实例路径、时间、策略等常量。B&P内部固定seed11，CG可修改CG_RANDOM_SEED。两个脚本原模型一致，根CG的目标27不能与原整数目标24混作同一种最优。

## 命令行示例

从仓库根目录运行：

```powershell
experiments/.venv/Scripts/python.exe code/milp/cplex_solver.py
experiments/.venv/Scripts/python.exe code/dwcg/dwcg_solver.py
experiments/.venv/Scripts/python.exe code/dwcg/dwcg_solver.py --strategy cg
experiments/.venv/Scripts/python.exe code/milp/cplex_solver.py code/data/tasks006_lines01_each06_seed13.json --time-limit 60
experiments/.venv/Scripts/python.exe code/dwcg/dwcg_solver.py code/data/tasks006_lines01_each06_seed13.json --time-limit 60
```

每次在 `code/results/cplex/` 或 `code/results/dwcg/` 建立带时间戳和随机后缀的独立目录，保存输入副本、配置和结果，不覆盖历史。CPLEX输出原约束验证的整数方案及原生状态/Best Bound；DW输出易读result.json，完整证明为certificate.sqlite。根CG/直接CPLEX另存原生日志，B&P以结构化证明记录为主。根CG的受限整数恢复没有全局整数证明含义。

退出码：0表示相应策略已完成最优/不可行证明（CG仅限LP）；2表示时限/节点限等未证完成；1表示程序/求解器错误。查看status及证明标志，不仅看是否有目标值。

这是便捷求解入口，软时限不保证包含所有后处理的硬实时墙钟预算；严格科研预算仍使用已有的外部worker实验入口。大实例可能超时，保留的可行整数利润和有效上界应分别阅读。
