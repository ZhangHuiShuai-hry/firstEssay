# 论文英文初稿

阅读入口：HCDP.pdf（正文）和HCDP_SF.pdf（补充文件）。主源文件HCDP.tex，章节在sections/，参考文献在MyReferences.bib。作者信息为明确占位，未使用模板样例的署名、基金或人物照片。

遵循用户提供的essay/模板副本/HCDP.tex：IEEEtran双栏、letter纸、现在时、五句摘要、短缩写、作者先于引用编号、斜体et al.、Input/Output伪代码、图表顶端浮动、8pt参考文献、正文不超过12页。正文7页，补充3页。模板中无效的lettersize选项修正为等价letterpaper，去除重复宏包以及cite/natbib冲突。模板原文件保持不动。

## 编译

在本目录运行PowerShell `./build.ps1`。需要TeX Live（IEEEtran、TikZ/PGFPlots、algorithmic、natbib、BibTeX）。脚本先编译正文，再运行BibTeX并复编译，最后编译补充文件，输出根目录两个PDF。build/为临时文件目录，不上传。

Overleaf可上传本目录全部LaTeX、bib、img/、sections/、tables/、data/runtime.csv，并以HCDP.tex为主文档、pdfLaTeX编译。补充文件另选HCDP_SF.tex。无需上传build/或原模板中的图片、照片与账户信息。

## 数据与证据

`scripts/export_evidence.py`从封存JSON/证书导出正文表格，复制双方共同的冻结输入到data/，不求解新实例；`scripts/export_structure.py`导出补充结构表。data/包含主600秒组、资源/边界180秒组、结构120/600秒组及正确性小例。source_manifest.json记录84项原始记录、输入和证书SHA。数值均源于实际旧运行，重导出不构成新性能实验。正文时间图由PGFPlots直接读取data/runtime.csv，未把超时点画成最优完成时间。

本稿方法是成熟的整线CG＋受限整数恢复＋按需资源档DP，对应sub/stage13/BASELINE.md，不是RL/adaptive_v1的新试验，也不是B&P树性能论文。相关全局最优结论区分CG界闭合与资源档DP闭合。待补项目、文献核验与模板执行情况见DRAFT_NOTES.md、REFERENCE_VERIFICATION.md、TEMPLATE_COMPLIANCE.md。

作者后续可直接修改源文件。当前SHA256.json用于标识本次交付字节，修订后应另行记录版本。用户模板及essay/qk.txt不会随本目录上传。
