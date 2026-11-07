# 英文论文第二版

阅读入口为 HCDP.pdf（正文）与 HCDP_SF.pdf（补充文件）。源码入口为 HCDP.tex，章节在 sections/，参考文献在 MyReferences.bib。第二版按用户指定的三篇期刊论文检查了结构和图文样式，保留本地 HCDP 模板的 IEEEtran 双栏、letter 纸、10 pt 正文及 12 页上限。正文现为 11 页，补充 3 页。

本版聚焦整线列生成、受限整数恢复和按需资源档 DP，不撰写强化学习方法或结果。原数学模型、求解器和历史实验保持不变；新的环形布局图只表示固定入口、单次通过的物理布置，OR 只表示 H/R/J 模式选择。图示风扇为概念例子，不是新增工业测试数据。

## 本轮修订

- 引言扩展到第二页中部以下，末尾包含指定引导句及三条编号贡献。
- 新增产品组件树、双线环形布局、AND 与模式 OR 示意；集合/参数/变量改为条目定义，约束 (2)–(13) 逐条解释。
- 新增算法流程概览与独立 Mermaid 源，见 MERMAID_GUIDE.md。
- 用 Python 绘制六组封存主实验的耗时和最终认证 Gap 折线图。限时点与证明完成点分开标记，保留失败边界案例。
- 参考文献扩展至 34 篇，全部在正文引用。主来源核对与年份冲突见 REFERENCE_VERIFICATION.md。

## 编译与图件

在本目录运行 PowerShell `./build.ps1`，需要 TeX Live 的 IEEEtran、algorithmic、natbib、BibTeX 等。得到两个根目录 PDF。build/ 为临时目录，不上传。Overleaf 以 HCDP.tex 为主文件、pdfLaTeX 编译即可；HCDP_SF.tex 单独编译。

`img/algorithm_flowchart.mmd` 可独立修改；导出为 `img/algorithm_flowchart.pdf` 后重新编译正文。其他图件由 `scripts/make_revision_figures.py` 生成，依赖 matplotlib、numpy、Pillow。PDF/SVG 保留文字，TIFF 为 600 dpi，PNG 为 300 dpi。运行该脚本会重建同名流程概览图，手工版请备份。

## 证据、检查与版本

`scripts/export_evidence.py` 与 export_structure.py 从封存实验导出表格与冻结输入，不运行新优化实验。84 项原始记录/输入/证书哈希见 data/source_manifest.json。性能图的逐点数据为 data/performance_lines.csv，来源为 data/formal600.json。反例和结构比较仍在正文/补充文件及原始数据中。

`scripts/check_draft.py` 检查引用、版式日志、正文页数、引言位置、逐条约束说明、图件审计和 84 项历史哈希，依赖 pypdf 与 PyMuPDF。qa/checks.json 和 qa/figures/ 保存实际检查结果；qa/revision2/ 为最终逐页预览。

**本版有效文件清单为 SHA256.v2.json**。运行 `python scripts/seal.py --check` 校验第二版。旧 SHA256.json 保留为第一版提交 e0715ad3 的快照，不能用它检查已经修改的第二版文件；必要时在该历史提交中核验。新清单不含自身，build/ 与 __pycache__/ 不进入清单。

作者署名、单位、基金、照片、实验机器 CPU 型号等仍待确认。模板、账户文件与外部论文原 PDF 不进入交付。完整本轮变更、检查范围和待补事项见 REVISION2_REPORT.md、DRAFT_NOTES.md、TEMPLATE_COMPLIANCE.md。
