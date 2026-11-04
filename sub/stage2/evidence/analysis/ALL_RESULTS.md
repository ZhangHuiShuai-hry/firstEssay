# 全部五组消融结果

首次LB秒数是run()算法时钟；总秒为父进程E2E。Compact首次发现时间未知。

|实例|方法|LB|UB|首次验证LB秒|E2E秒|已证整数最优|预算内|
|---|---|---:|---:|---:|---:|---|---|
|existing20_original|compact|132.5800|132.5800|—|3.9486|True|True|
|existing20_original|baseline|132.5800|132.5800|0.7189|2.0415|True|True|
|existing20_original|short|132.5800|132.5800|0.8887|2.4706|True|True|
|existing20_original|quota|132.5800|132.5800|0.8827|2.0437|True|True|
|existing20_original|short_quota|132.5800|132.5800|0.8307|1.7778|True|True|
|tasks020_resource_H2_R2|baseline|131.5800|131.5800|1.0056|2.8595|True|True|
|tasks020_resource_H2_R2|short|131.5800|131.5800|1.2720|3.1482|True|True|
|tasks020_resource_H2_R2|quota|131.5800|131.5800|1.2929|3.3664|True|True|
|tasks020_resource_H2_R2|short_quota|131.5800|131.5800|1.0972|3.2620|True|True|
|tasks020_resource_H2_R2|compact|131.5800|131.5800|—|2.6674|True|True|
|tasks020_resource_H1_R2|short|122.7500|122.7500|1.0728|2.8172|True|True|
|tasks020_resource_H1_R2|quota|122.7500|122.7500|1.1661|2.7076|True|True|
|tasks020_resource_H1_R2|short_quota|122.7500|122.7500|1.1245|2.7151|True|True|
|tasks020_resource_H1_R2|compact|122.7500|122.7500|—|1.4055|True|True|
|tasks020_resource_H1_R2|baseline|122.7500|122.7500|1.1350|2.5009|True|True|
|existing40_original|quota|305.8300|305.8300|24.7967|25.9092|True|True|
|existing40_original|short_quota|302.8300|323.6813|1.9235|28.9745|False|True|
|existing40_original|compact|305.8300|316.9316|—|29.9948|False|True|
|existing40_original|baseline|305.8300|305.8300|26.0186|27.8706|True|True|
|existing40_original|short|305.8300|305.8300|1.8202|28.5475|True|True|
