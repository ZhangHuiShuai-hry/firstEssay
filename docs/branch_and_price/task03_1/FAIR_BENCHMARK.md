# 30秒受控 pilot

输入每例只生成一次，worker 校验同一份冻结 JSON 的原始字节 SHA。新源码快照为 source_snapshot。全部方法单线程CPLEX、seed11、相同数值政策，串行独立进程，交替方法次序。时间从启动进程前算起，含导入和可复核结果落盘。外层非硬实时：超限如实记录；迟到结果不采纳最优证明。

|seed|方法|状态|LB|UB|绝对Gap|相对Gap|实际秒(含accounting)|超秒|硬停止|最终结果采纳|证据bytes|
|---|---|---|---|---|---|---|---|---|---|---|---|
|11|V0|time_limit|null|312.46865|null|null|29.54433|0|False|True|1966080|
|11|V1|time_limit|null|null|null|null|30.00766|0.00766|True|False|16384|
|11|V2|time_limit|null|null|null|null|30.01776|0.01776|True|False|2322432|
|11|V3|time_limit|301.43000|null|null|null|30.01829|0.01829|True|False|36864|
|11|Compact|time_limit|305.83000|315.53657|9.70657|0.03174|24.40873|0|False|True|393216|
|21|Compact|time_limit|341.30000|353.96668|12.66668|0.03711|24.41380|0|False|True|397312|
|21|V3|time_limit|336.50000|null|null|null|30.02803|0.02803|True|False|40960|
|21|V2|time_limit|null|null|null|null|30.00912|0.00912|True|False|16384|
|21|V1|time_limit|null|null|null|null|30.00793|0.00793|True|False|16384|
|21|V0|time_limit|null|null|null|null|30.02307|0.02307|True|False|2015232|
|31|V0|time_limit|null|null|null|null|30.66159|0.66159|True|False|16384|
|31|V1|time_limit|null|null|null|null|30.05936|0.05936|True|False|16384|
|31|V2|time_limit|null|null|null|null|30.01076|0.01076|True|False|16384|
|31|V3|time_limit|303.83000|null|null|null|30.04121|0.04121|True|False|36864|
|31|Compact|time_limit|303.93000|316.34434|12.41434|0.04085|24.42816|0|False|True|393216|
|41|Compact|time_limit|299.22000|311.38684|12.16684|0.04066|24.45966|0|False|True|393216|
|41|V3|time_limit|297.42000|null|null|null|30.03714|0.03714|True|False|40960|
|41|V2|time_limit|null|305.23081|null|null|27.36299|0|False|True|2248704|
|41|V1|time_limit|null|null|null|null|30.02068|0.02068|True|False|1732608|
|41|V0|time_limit|null|314.91315|null|null|29.75960|0|False|True|1908736|
|51|V0|time_limit|null|372.17978|null|null|29.20907|0|False|True|1867776|
|51|V1|time_limit|null|null|null|null|30.01377|0.01377|True|False|16384|
|51|V2|time_limit|null|367.61333|null|null|25.48671|0|False|True|2293760|
|51|V3|time_limit|358.28000|367.61333|9.33333|0.02605|27.20225|0|False|True|2048000|
|51|Compact|time_limit|359.68000|374.30819|14.62819|0.04067|24.44158|0|False|True|389120|

完整数据、内存和exclusive profile总和见 FAIR_BENCHMARK.json；逐函数profile位于每臂 SQLite 的 metrics 根。硬停止时未完成的profile不会伪造补齐；内存可能null，不能当零。首解记录是原算法API内相对时间，未补全进程启动偏移，不能作为精确E2E首解比较。

被停止的方法只采纳已提交的初始保守checkpoint；可能只有V3的已验证整数LB，而没有UB。不能把没有及时完整证书解释为数学不可行，也不能假设根LP已收敛或树太大。未运行n30/40和120秒扩展；应先解决轮级checkpoint及剖析缺项。

原始开发scout不用于本表；新固定10秒scout另存scout_fixed。总墙钟公平性仍为PARTIAL：统一外层deadline和迟到证明拒绝已经实现，但Windows调度超限、accounting收尾和逐函数剖析开销限制了严格墙钟解释。
