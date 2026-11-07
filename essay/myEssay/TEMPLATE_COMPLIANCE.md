# HCDP模板执行记录

实际阅读本地HCDP.tex的1296行，包括前部写作要求、正文结构、实验/结论说明与附录结构。私人账户、示例资助及联系方式不进入新稿或版本库。参考HCDP_SF.tex建立补充文档。以下以本地模板为主，期刊PDF为版式辅助。

|模板要求|执行|
|---|---|
|六项结构：img、SFimg、photo、MyReferences.bib、HCDP_SF.tex、HCDP.tex|全部建立；未确认照片以目录说明替代|
|IEEEtran期刊双栏、letter、12页以内|正文11页，补充3页；使用正确的letterpaper选项|
|现在时、短句、this work|按要求起草；没有this paper或将来时承诺|
|摘要五句：背景/问题/模型/方法/结果|按五句组织；无不必要缩写|
|正文缩写首次展开、最多5字母|DLBP/MILP/LP/CG/RMP/DP/LB/UB；H/R/J为模式符号|
|图表顶部/底部浮动|全部使用[!t]；每张主要图表有相应说明段落|
|图中文字清晰并匹配正文|原创Python矢量PDF/SVG，全部图中文字10pt；600 dpi TIFF备用，不使用模板位图|
|Input/Output伪代码，动词开头|Algorithm 1使用Input/Output，步骤以Generate、Record、Solve等开头|
|小写参数、大写集合、符号不重名|条目式符号定义统一；变量/列量上下文明确，避免把全局资源放进完整局部域|
|作者姓名先于编号、et al.斜体|引言作者叙述后引用，使用统一etal宏|
|参考文献8pt，IEEEtran，姓+年份键|34条均引用，公开主来源题录/可访问摘要核对，经典理论为必要的年份例外|
|优先课题组及近五年文献|包含直接相关的课题组协作/资源共享/疲劳工作；没有为了数量引用无关文章|
|新案例、小中大规模、CPLEX及近年算法比较|保留现有合成参考和80/120任务实例；没有工业案例或新算法比较，明确列为待补|
|Note to Practitioners|模板说明仅TASE投稿时使用；此稿目标参考IJAIGM，不加入不适用栏目|
|作者简介/基金等|明确待确认，不复制模板示例|

样例模板同时载入cite和natbib、重复算法宏包，且lettersize不是该IEEEtran版本接受的选项。新稿保留相同双栏外观，移除冲突/重复并改用letterpaper；不照搬模板排版错误。

网站参考：IJAIGM author guidelines（https://hopeembark.org/index.php/IJGMAI/about/submissions），Gu等共享运输论文PDF（https://hopeembark.org/index.php/IJGMAI/article/download/39/35/574），Zhou等疲劳论文PDF（https://hopeembark.org/index.php/IJGMAI/article/download/50/25/584）。核对日期2026-11-07。采用双栏、章节编号、图表/参考文献风格；没有复制图表内容或publisher/received/accepted声明。

第二版依据用户更具体的要求，用条目定义替代符号表；引言延至第二页中部以下并以三条编号贡献结束；约束(2)–(13)逐条解释；新增独立Mermaid及真实主实验折线图。图密集页使用raggedbottom维持自然段距，作者/图片最终确认后可按投稿要求继续调整。三篇用户指定期刊例文的阅读与字段冲突见REFERENCE_VERIFICATION.md。
