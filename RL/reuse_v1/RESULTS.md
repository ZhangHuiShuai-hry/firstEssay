# 在线同引擎对照

每项一次开发运行，不是显著性实验；中例60秒软预算，两种配置实际均在预算内结束。LB/UB使用未格式化原值核验，表格仅显示8位。

|实例|整数LB|对照UB|对照算法秒|复用算法秒|原生PP次数|状态|
|---|---:|---:|---:|---:|---|---|
|tiny5|24.0|24.00000000|0.8264|0.4144|10→10|optimal_within_tolerance|
|tiny6|56.629999999999995|56.63000000|0.2547|0.2612|1→1|optimal_within_tolerance|
|lp_yes_ip_no|None|4.00000000|0.3503|0.2719|6→4|lp_optimal_integer_unproven|
|n80s32|583.64|583.64000000|19.2046|20.4793|20→20|optimal_within_tolerance|
|n120tight32|927.46|927.46000000|32.9675|30.3090|36→33|optimal_within_tolerance|

原结果的timing.PP_native_seconds与pricing_strategy来自被price_override绕过的旧工厂，不能作为实际PP耗时和策略；实际为逐线persistent warm，完整事件见pricing_native_events，正确分项见evidence/metrics.json。algorithm_seconds含会话释放，最终持久化及accounting另存。没有把微小耗时波动解释为确定的机制收益。
