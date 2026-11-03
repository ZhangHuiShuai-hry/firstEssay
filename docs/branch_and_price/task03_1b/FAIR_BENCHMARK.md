# Task03.1b 30秒受控 pilot

输入每例只生成一次，worker 校验同一份冻结 JSON 的原始字节 SHA，并在离线审计确认与Task03.1五个冻结输入字节相同。源码快照为 source_snapshot。全部方法单线程CPLEX、seed11、相同数值政策，串行独立进程，交替方法次序。时间含导入和可复核结果落盘；admission回执绑定accounting SHA。外层非硬实时：超限如实记录。

|seed|方法|状态|LB|UB|绝对Gap|相对Gap|实际秒(含accounting)|超秒|硬停止|最终结果采纳|证据bytes|
|---|---|---|---|---|---|---|---|---|---|---|---|
|11|V0|time_limit|null|339.75895|null|null|25.75550|0|False|True|1286144|
|11|V1|time_limit|null|324.17989|null|null|25.45944|0|False|True|1196032|
|11|V2|time_limit|null|328.94275|null|null|25.34384|0|False|True|1224704|
|11|V3|time_limit|301.43000|331.37238|29.94238|0.09933|25.64432|0|False|True|1265664|
|11|Compact|time_limit|305.83000|317.24717|11.41717|0.03733|25.65078|0|False|True|397312|
|21|Compact|time_limit|341.30000|353.99476|12.69476|0.03720|25.32283|0|False|True|393216|
|21|V3|time_limit|336.40000|361.16194|24.76194|0.07361|25.34989|0|False|True|1286144|
|21|V2|time_limit|null|361.16194|null|null|25.52031|0|False|True|1187840|
|21|V1|time_limit|null|364.02538|null|null|25.62444|0|False|True|1167360|
|21|V0|time_limit|null|1047.34148|null|null|25.45322|0|False|True|1179648|
|31|V0|time_limit|null|719.94716|null|null|25.36706|0|False|True|1142784|
|31|V1|time_limit|null|318.71481|null|null|25.26773|0|False|True|1183744|
|31|V2|time_limit|null|318.00171|null|null|25.71052|0|False|True|1187840|
|31|V3|time_limit|303.83000|324.04748|20.21748|0.06654|25.46120|0|False|True|1212416|
|31|Compact|time_limit|303.93000|318.08111|14.15111|0.04656|25.24407|0|False|True|393216|
|41|Compact|time_limit|299.22000|312.40425|13.18425|0.04406|25.40765|0|False|True|389120|
|41|V3|time_limit|297.42000|311.87115|14.45115|0.04859|25.50570|0|False|True|1327104|
|41|V2|time_limit|null|310.59739|null|null|25.60706|0|False|True|1273856|
|41|V1|time_limit|null|321.55576|null|null|25.43289|0|False|True|1241088|
|41|V0|time_limit|null|846.56369|null|null|25.34064|0|False|True|1200128|
|51|V0|time_limit|null|414.67775|null|null|25.54128|0|False|True|1265664|
|51|V1|time_limit|null|378.56603|null|null|25.39217|0|False|True|1224704|
|51|V2|time_limit|null|379.48274|null|null|25.68054|0|False|True|1187840|
|51|V3|time_limit|358.28000|379.98254|21.70254|0.06057|25.44684|0|False|True|1216512|
|51|Compact|time_limit|359.68000|375.36857|15.68857|0.04362|25.63116|0|False|True|393216|

完整数据、内存和exclusive profile总和见 FAIR_BENCHMARK.json；逐函数profile位于每臂 SQLite 的 metrics 根。first_integer_end_to_end_seconds 加入进程偏移；Compact内部首解时刻未知为null。

被停止的方法只采纳已提交的初始保守checkpoint；可能只有V3的已验证整数LB，而没有UB。不能把没有及时完整证书解释为数学不可行，也不能假设根LP已收敛或树太大。未运行n30/40和120秒扩展；应先解决轮级checkpoint及剖析缺项。

完整恢复NOT IMPLEMENTED，没有把初始LB摘要当可恢复搜索。总墙钟定义包括accounting完成；独立admission回执属于观测日志，其自身发布时间不递归计量，不声称绝对硬实时。cProfile开销计费，不能把不同树的总时间差全部归为接口优化。
