# 整线方案列生成数学说明

`main.tex` 对应 `sub/` 当前整线分解路线，源码基线 `b534b8ad`。与 `problem/dwcg/` 的工作站列不同，一列是一条线的完整整数方案；原模型目标和物理约束保留。文档包含符号、完整局部列域、主问题/对偶/定价、两阶段可行性、整数恢复/资源档、有效界、代码对应、迭代统计与线数因素实验。

在本目录运行两次：

```powershell
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

`main.pdf` 是阅读版本。结构实验中提出的线数组合是后续实验设计，未标记为已运行。现有结果分别保留方法版本与证书边界，不把受限整数主问题或根 LP 收敛当作一般整数最优证明。

本次文档已用 XeLaTeX (TeX Live 2026) 编译并完成交叉引用复编译，最终为10页；最终日志无 LaTeX Warning、Overfull 或 Underfull，10页已渲染检查。对照了原始局部约束、主问题、阶段9经济界和实际迭代记录。本次仅新增文档，未修改求解算法或重新执行性能实验。
