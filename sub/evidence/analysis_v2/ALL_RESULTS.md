# 自动生成的全部实验结果

利润/UB 均为最大化口径。时间为父进程端到端实测秒。
station 是已有根 CG + 周期受限 IP；line 是整线分解 + 受限 IP。
超时不等于不可行；仅 `证明=True` 表示已闭合整数最优证书。

## pilot_v1

|实例|方法|LB|UB|绝对Gap|秒|预算内|整数最优证明|状态|
|---|---|---:|---:|---:|---:|---|---|---|
|tiny5_original|compact|24.0000|24.0000|0.0000|1.9287|True|True|optimal|
|tiny5_original|station|24.0000|27.0000|3.0000|2.6244|True|False|node_lp_optimal_proven|
|tiny5_original|line|24.0000|24.0000|0.0000|2.1833|True|True|optimal_within_tolerance|
|tiny6_original|station|54.4800|59.3800|4.9000|2.4055|True|False|node_lp_optimal_proven|
|tiny6_original|line|56.6300|56.6300|0.0000|1.7316|True|True|optimal_within_tolerance|
|tiny6_original|compact|56.6300|56.6300|0.0000|1.8101|True|True|optimal|
|existing20_original|line|132.5800|132.5800|0.0000|2.3516|True|True|optimal_within_tolerance|
|existing20_original|compact|132.5800|132.5800|0.0000|3.2527|True|True|optimal|
|existing20_original|station|131.1200|137.8657|6.7457|4.1057|True|False|node_lp_optimal_proven|
|existing40_original|station|—|331.5154|—|15.3427|False|False|time_limit|
|existing40_original|line|305.8300|—|—|15.2589|False|False|time_limit|
|existing40_original|compact|305.4300|319.4271|13.9971|15.9671|False|False|time_limit|

## ablation_v2

|实例|方法|LB|UB|绝对Gap|秒|预算内|整数最优证明|状态|
|---|---|---:|---:|---:|---:|---|---|---|
|existing20_original|line|132.5800|132.5800|0.0000|2.3346|True|True|optimal_within_tolerance|
|existing20_original|compact|132.5800|132.5800|0.0000|2.8989|True|True|optimal|
|existing20_original|station|131.1200|137.8657|6.7457|3.9810|True|False|node_lp_optimal_proven|
|existing20_no_precedence|compact|132.5800|132.5800|0.0000|2.0052|True|True|optimal|
|existing20_no_precedence|station|131.1200|137.8657|6.7457|3.9091|True|False|node_lp_optimal_proven|
|existing20_no_precedence|line|132.5800|132.5800|0.0000|2.3417|True|True|optimal_within_tolerance|
|existing20_no_fatigue|station|131.1200|137.8657|6.7457|3.9822|True|False|node_lp_optimal_proven|
|existing20_no_fatigue|line|132.5800|132.5800|0.0000|2.7801|True|True|optimal_within_tolerance|
|existing20_no_fatigue|compact|132.5800|132.5800|0.0000|2.9648|True|True|optimal|
|existing20_resource_ample|line|132.5800|132.5800|0.0000|2.0499|True|True|optimal_within_tolerance|
|existing20_resource_ample|compact|132.5800|132.5800|0.0000|1.9623|True|True|optimal|
|existing20_resource_ample|station|131.1200|137.8657|6.7457|4.7702|True|False|node_lp_optimal_proven|
|existing20_resource_tight|compact|132.5800|132.5800|0.0000|3.7257|True|True|optimal|
|existing20_resource_tight|station|131.1200|137.8657|6.7457|4.5507|True|False|node_lp_optimal_proven|
|existing20_resource_tight|line|132.5800|132.5800|0.0000|2.5257|True|True|optimal_within_tolerance|
|existing40_original|station|—|351.2036|—|14.0605|True|False|time_limit|
|existing40_original|line|305.8300|311.3132|5.4832|13.8865|True|False|time_limit|
|existing40_original|compact|305.4300|319.3405|13.9105|14.2397|True|False|time_limit|
|existing40_no_precedence|line|320.9400|320.9400|0.0000|2.6250|True|True|optimal_within_tolerance|
|existing40_no_precedence|compact|320.9400|320.9400|0.0000|6.1164|True|True|optimal|
|existing40_no_precedence|station|187.4400|342.8353|155.3953|13.8842|True|False|time_limit|
|existing40_no_fatigue|compact|307.0300|321.5542|14.5242|14.3633|True|False|time_limit|
|existing40_no_fatigue|station|—|341.1266|—|13.9529|True|False|time_limit|
|existing40_no_fatigue|line|307.1300|315.2375|8.1075|14.2093|True|False|time_limit|
|existing40_resource_ample|station|—|332.7512|—|13.8689|True|False|time_limit|
|existing40_resource_ample|line|305.8300|311.6574|5.8274|13.7147|True|False|time_limit|
|existing40_resource_ample|compact|305.8300|306.1933|0.3633|13.8890|True|False|time_limit|
|existing40_resource_tight|line|305.8300|311.1451|5.3151|13.5981|True|False|time_limit|
|existing40_resource_tight|compact|304.0300|318.0270|13.9970|14.2504|True|False|time_limit|
|existing40_resource_tight|station|—|332.7512|—|13.8821|True|False|time_limit|

## line_counts_v2

|实例|方法|LB|UB|绝对Gap|秒|预算内|整数最优证明|状态|
|---|---|---:|---:|---:|---:|---|---|---|
|tasks040_lines02_seed11|compact|320.1300|327.0836|6.9536|13.5097|True|False|time_limit|
|tasks040_lines02_seed11|line|320.1300|321.7908|1.6608|13.2431|True|False|time_limit|
|tasks040_lines04_seed11|line|322.1900|322.1900|0.0000|0.7590|True|True|optimal_within_tolerance|
|tasks040_lines04_seed11|compact|322.1900|322.1900|0.0000|0.9664|True|True|optimal|
|tasks040_lines02_seed12|compact|254.4100|268.2585|13.8485|13.6219|True|False|time_limit|
|tasks040_lines02_seed12|line|254.4100|254.4100|0.0000|9.2509|True|True|optimal_within_tolerance|
|tasks040_lines04_seed12|line|257.3700|257.3700|0.0000|1.5089|True|True|optimal_within_tolerance|
|tasks040_lines04_seed12|compact|257.3700|257.3700|-0.0000|1.4807|True|True|optimal|
|tasks040_lines02_seed13|compact|383.3400|401.8604|18.5204|13.8608|True|False|time_limit|
|tasks040_lines02_seed13|line|385.4400|395.3000|9.8600|13.3924|True|False|time_limit|
|tasks040_lines04_seed13|line|371.0400|371.0400|0.0000|1.9122|True|True|optimal_within_tolerance|
|tasks040_lines04_seed13|compact|371.0400|374.6501|3.6101|13.7004|True|False|time_limit|

## resource_stress_v2

|实例|方法|LB|UB|绝对Gap|秒|预算内|整数最优证明|状态|
|---|---|---:|---:|---:|---:|---|---|---|
|tasks020_resource_H2_R2|compact|131.5800|131.5800|0.0000|1.6275|True|True|optimal|
|tasks020_resource_H2_R2|station|131.1200|135.5300|4.4100|4.3582|True|False|node_lp_optimal_proven|
|tasks020_resource_H2_R2|line|131.5800|131.5800|0.0000|2.2573|True|True|optimal_within_tolerance|
|tasks020_resource_H1_R2|station|122.2900|126.7000|4.4100|3.8842|True|False|node_lp_optimal_proven|
|tasks020_resource_H1_R2|line|122.7500|122.7500|0.0000|2.5419|True|True|optimal_within_tolerance|
|tasks020_resource_H1_R2|compact|122.7500|122.7500|0.0000|2.0056|True|True|optimal|
|tasks020_resource_H1_R1|line|99.1300|99.1300|0.0000|3.0962|True|True|optimal_within_tolerance|
|tasks020_resource_H1_R1|compact|99.1300|99.1300|0.0000|2.5615|True|True|optimal|
|tasks020_resource_H1_R1|station|99.1300|99.1300|0.0000|4.6847|True|True|node_lp_optimal_proven|

