# 算法流程图修改与编译

可直接编辑或复制 `img/algorithm_flowchart.mmd` 到支持 Mermaid 的编辑器。该文件包含 Phase I/II、完整定价判定、整数恢复、资源档 DP、时间终止及不可行证明分支。正文伪代码仍为算法细节的正式说明。

当前正文已包含一张 Python 绘制的流程概览图，可以直接编译。自行调整 Mermaid 后，请导出 **PDF**，命名为 **`algorithm_flowchart.pdf`**，放入 **`essay/myEssay/img/`**，替换该目录下的同名图。保留白色背景，裁掉外部空白，按正文全栏宽约 18.2 cm 检查文字可读性。不要仅把 PNG 扩展名改成 PDF。

主文档的调用已写好：

```latex
\includegraphics[width=\textwidth]{img/algorithm_flowchart.pdf}
```

然后在 `essay/myEssay` 中运行：

```powershell
./build.ps1
```

即可得到新的 `HCDP.pdf`，无需修改 LaTeX 图片路径。如果只导出 PNG，则将调用中的 `.pdf` 改为 `.png`；建议至少 300 dpi。PDF/SVG 更适合保留矢量文字。重新运行 `scripts/make_revision_figures.py` 会重建 Python 版同名图片，因此手工调整版应另外备份。

图中 OR 的适用范围：只用于“是否选中的任务采用哪种 H/R/J 模式”。它不是新的拆卸路径 OR，流程图中的判断分支也不是新增的模型约束。
