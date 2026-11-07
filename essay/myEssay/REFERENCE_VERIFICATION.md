# 文献与来源核对（第二版，2026-11-07）

只对已查到的主来源摘要/元数据作有限归纳；受限全文没有假装已读。未将模板MyReferences.bib整体复制。第一版10条BibTeX条目均实际引用，作者名在前、姓在后，IEEE样式自动排版。文章号期刊没有传统页码/期号时使用官方文章号，不虚构字段。

|键|主来源与核对范围|说明|
|---|---|---|
|Guo2021|https://www.ieee-jas.com/article/doi/10.1109/JAS.2020.1003515?pageType=en&viewType=HTML |8(7),1308--1324,2021,DOI；修正模板示例漏掉的Abdullah Abusorrah作者|
|Guo2024a|https://digitalcommons.njit.edu/fac_pubs/1157/ |7作者，21(3),4448--4459,2024；DOI含2023是early-access年份，不替代卷期2024|
|Guo2024|https://www.sciencedirect.com/science/article/pii/S0736584524001030 |官方索引摘要及元数据：90,102816,2024；完整正文请求403，没有据此描述未见细节|
|Chu2025|https://doi.org/10.1080/00207543.2025.2452385 |2作者，63(12),4478--4503,2025，摘要支持两侧部分拆卸范围|
|Huang2025|https://www.sciencedirect.com/science/article/pii/S0278612525000342 |6作者，80,38--69,2025，官方摘要支持U形/开关策略|
|Guo2025|https://researchwith.montclair.edu/en/publications/modeling-and-optimization-of-multiproduct-humanrobot-collaborativ/ |7作者，12(5),2848--2863,2025；资源共享不是本稿首次引入，研究定位明确说明|
|Gu2025|https://hopeembark.org/index.php/IJGMAI/article/download/39/35/574 |期刊原PDF共13页，页码1--13；1(1),2025，6作者、DOI与期刊页面匹配|
|Zhou2025|https://hopeembark.org/index.php/IJGMAI/article/download/50/25/584 |原PDF卷期1(2),June2025，页码93--107；网页Published/How-to-cite显示2026，与PDF不一致，采用PDF卷期年2025，投稿前建议向期刊确认|
|Dantzig1960|https://pubsonline.informs.org/doi/abs/10.1287/opre.8.1.101 |2作者，8(1),101--111，1960；经典理论来源，近五年要求的必要例外|
|Lubbecke2005|https://pubsonline.informs.org/doi/abs/10.1287/opre.1050.0234 |2作者，53(6),1007--1023，2005；经典CG理论来源，保留原始贡献归属|

网络来源的文献信息只用于本地新稿与核验说明，没有上传用户模板中的账号信息。引用核对不等于完整系统综述；论文最终新颖性定位、同题现有方法比较与正文受限文献的深入阅读仍需作者进一步完成。


## 第二版新增核对与完整索引

第二版共 34 篇，全部出现在正文引用中；新增 24 篇。公开 DOI 元数据保存于 data/literature_v2/metadata.json，按题名查询后精确匹配的四条候选保存在 query_candidates.json，采用条目见 verified_index.json。没有把搜索结果排名自动当作相关性证据。正文只采用题名/可访问主来源摘要支持的研究范围，不归纳无法访问的全文算法细节或未读结果。Guo2024a 的本次 Crossref 请求失败，保留上表已经由 NJIT 主来源核对的原条目；没有把本次失败标作新访问成功。

字段人工纠正：Güler 条目中 Crossref 将 Mehmet Ali Ilgin 的姓拆为 Ali Ilgin，BibTeX 采用 Mehmet Ali / Ilgin；du Merle 与 Goksoy Kalaycilar 的复合姓使用逗号格式保留；Fang 的 online 年为 2023、卷期年为 2024，采用 2024；Özceylan 综述 online 年为 2018、卷期年为 2019，采用 2019。Zhang 的期刊原 PDF 页眉明确 Vol.1 No.2 June 2025、页码 69–79，而网页/元数据年份有 2026，采用印刷卷期 2025。Zhou 同类冲突保留原说明。投稿前仍建议向期刊确认这两条的年份差异。

|键|公开主来源|本轮范围|
|---|---|---|
|Alfandi2025|[10.1080/00207543.2024.2449241](https://doi.org/10.1080/00207543.2024.2449241)|DOI 题录取得；正文限于已支持的主题范围|
|Barnhart1998|[10.1287/opre.46.3.316](https://doi.org/10.1287/opre.46.3.316)|DOI 题录取得；正文限于已支持的主题范围|
|Battaia2022|[10.1016/j.ijpe.2022.108673](https://doi.org/10.1016/j.ijpe.2022.108673)|DOI 题录取得；正文限于已支持的主题范围|
|Boysen2022|[10.1016/j.ejor.2021.11.043](https://doi.org/10.1016/j.ejor.2021.11.043)|DOI 题录取得；正文限于已支持的主题范围|
|Chu2025|[10.1080/00207543.2025.2452385](https://doi.org/10.1080/00207543.2025.2452385)|DOI 题录取得；正文限于已支持的主题范围|
|Dantzig1960|[10.1287/opre.8.1.101](https://doi.org/10.1287/opre.8.1.101)|DOI 题录取得；正文限于已支持的主题范围|
|Fang2024|[10.1080/00207543.2023.2251064](https://doi.org/10.1080/00207543.2023.2251064)|DOI 题录取得；正文限于已支持的主题范围|
|GoksoyKalaycilar2024|[10.1016/j.cie.2024.110089](https://doi.org/10.1016/j.cie.2024.110089)|DOI 题录取得；正文限于已支持的主题范围|
|Gu2025|[10.67119/2971lk72](https://doi.org/10.67119/2971lk72)|DOI 题录取得；正文限于已支持的主题范围|
|Guler2024|[10.1016/j.cie.2024.109898](https://doi.org/10.1016/j.cie.2024.109898)|DOI 题录取得；正文限于已支持的主题范围|
|Guo2021|[10.1109/jas.2020.1003515](https://doi.org/10.1109/jas.2020.1003515)|DOI 题录取得；正文限于已支持的主题范围|
|Guo2023|[10.1109/tcss.2022.3217101](https://doi.org/10.1109/tcss.2022.3217101)|DOI 题录取得；正文限于已支持的主题范围|
|Guo2024|[10.1016/j.rcim.2024.102816](https://doi.org/10.1016/j.rcim.2024.102816)|DOI 题录取得；正文限于已支持的主题范围|
|Guo2024a|[10.1109/TASE.2023.3296733](https://doi.org/10.1109/TASE.2023.3296733)|既有机构主来源保留；本次 API 不可用|
|Guo2025|[10.1109/tcss.2025.3540070](https://doi.org/10.1109/tcss.2025.3540070)|DOI 题录取得；正文限于已支持的主题范围|
|He2024|[10.1016/j.ijpe.2024.109257](https://doi.org/10.1016/j.ijpe.2024.109257)|DOI 题录取得；正文限于已支持的主题范围|
|Huang2025|[10.1016/j.jmsy.2025.02.004](https://doi.org/10.1016/j.jmsy.2025.02.004)|DOI 题录取得；正文限于已支持的主题范围|
|Laili2020|[10.1016/j.jmsy.2020.07.015](https://doi.org/10.1016/j.jmsy.2020.07.015)|DOI 题录取得；正文限于已支持的主题范围|
|Lubbecke2005|[10.1287/opre.1050.0234](https://doi.org/10.1287/opre.1050.0234)|DOI 题录取得；正文限于已支持的主题范围|
|Maher2023|[10.1007/s12532-023-00240-w](https://doi.org/10.1007/s12532-023-00240-w)|DOI 题录取得；正文限于已支持的主题范围|
|Otto2011|[10.1016/j.ejor.2011.01.056](https://doi.org/10.1016/j.ejor.2011.01.056)|DOI 题录取得；正文限于已支持的主题范围|
|Ozceylan2019|[10.1080/00207543.2018.1428775](https://doi.org/10.1080/00207543.2018.1428775)|DOI 题录取得；正文限于已支持的主题范围|
|Parsa2021|[10.1016/j.rcim.2021.102170](https://doi.org/10.1016/j.rcim.2021.102170)|DOI 题录取得；正文限于已支持的主题范围|
|Pessoa2020|[10.1007/s10107-020-01523-z](https://doi.org/10.1007/s10107-020-01523-z)|DOI 题录取得；正文限于已支持的主题范围|
|Wu2023|[10.1016/j.eswa.2023.120589](https://doi.org/10.1016/j.eswa.2023.120589)|DOI 题录取得；正文限于已支持的主题范围|
|Wu2024|[10.1016/j.engappai.2024.108703](https://doi.org/10.1016/j.engappai.2024.108703)|DOI 题录取得；正文限于已支持的主题范围|
|Xiao2024|[10.1051/mfreview/2024015](https://doi.org/10.1051/mfreview/2024015)|DOI 题录取得；正文限于已支持的主题范围|
|Xu2021|[10.1016/j.jclepro.2021.129158](https://doi.org/10.1016/j.jclepro.2021.129158)|DOI 题录取得；正文限于已支持的主题范围|
|Xu2024|[10.1016/j.eswa.2023.122323](https://doi.org/10.1016/j.eswa.2023.122323)|DOI 题录取得；正文限于已支持的主题范围|
|Yin2025|[10.1016/j.jclepro.2025.144695](https://doi.org/10.1016/j.jclepro.2025.144695)|DOI 题录取得；正文限于已支持的主题范围|
|Zhang2025|[10.67119/6413dhny](https://doi.org/10.67119/6413dhny)|DOI 题录取得；正文限于已支持的主题范围|
|Zhou2025|[10.67119/7936arid](https://doi.org/10.67119/7936arid)|DOI 题录取得；正文限于已支持的主题范围|
|Zhu2024|[10.1016/j.cie.2024.110621](https://doi.org/10.1016/j.cie.2024.110621)|DOI 题录取得；正文限于已支持的主题范围|
|duMerle1999|[10.1016/s0012-365x(98)00213-1](https://doi.org/10.1016/s0012-365x(98)00213-1)|DOI 题录取得；正文限于已支持的主题范围|


## 用户指定的期刊格式例文

- [57/33](https://hopeembark.org/index.php/IJGMAI/article/view/57/33)：原 PDF 11 页；引言延至第二页、三条编号贡献；其循环加工定义不引入本稿。
- [45/28](https://hopeembark.org/index.php/IJGMAI/article/view/45/28)：原 PDF 11 页；人机协作利润主题、问题图和约束后说明可作格式参考；本稿没有复用其模型/数据/图片。
- [63/41](https://hopeembark.org/index.php/IJGMAI/article/view/63/41)：原 PDF 12 页；编号贡献和 Problem Description 的组织方式作为版式参考。

三篇格式原 PDF 均实际下载阅读，暂存忽略的 build/reference_pdfs/。57/63 的学习算法不进入本稿方法或结果，也没有仅因格式用途将它们塞入参考文献。网页与 DOI 题录访问日期为 2026-11-07；部分网页显示时间不同于印刷年份，以上显式记录。
