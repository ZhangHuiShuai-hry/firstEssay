# 短初始化与配额补列实验入口

报告：[REPORT.md](REPORT.md)。新增求解器：[solver.py](solver.py)。旧sub、stage1、problem与code源码未改。

```powershell
# 单实例运行：short / quota / short_quota；输出目录必须新建
experiments/.venv/Scripts/python.exe sub/stage2/paired.py --worker short --instance code/data/tasks040_lines02_each20_seed11.json --output sub/stage2/evidence/my_short --budget 30

# 完整五组消融：Compact、旧整线、短初始化、配额、短初始化+配额
experiments/.venv/Scripts/python.exe sub/stage2/paired.py --output sub/stage2/evidence/my_pair --budget 30

# 新单元测试
experiments/.venv/Scripts/python.exe -m unittest discover -s sub/stage2 -p test_solver.py -v
```

库接口：`run(data,time_limit=30,init_seconds=.5,quota=True)`。函数签名默认init_seconds=None、quota=False，保持旧初始化行为；short/short_quota显式设为0.5。配额默认单次最多4个PP、2秒，其时间包括在同一软预算内。每次RIP与最终见证都检查原模型约束，补列不承担全域定价证书。

运行输出压缩JSON可用`zlib.decompress`读取；summary保存输入与源码SHA。stage2_verify.audit用于V3独立重放，enumerate_pricing=True会完整枚举微型输入。validate_suite.py用于本批20份小规模与20份配对的完整复验；它创建新validation目录以防覆盖，已有目录时会报错，重跑请先在脚本中指定新的实验输出路径。

原始数据在evidence/paired30，完整表在evidence/analysis/ALL_RESULTS.md，40份验证记录在evidence/validation/summary.json。SHA256.json覆盖本阶段全部文件；父目录旧哈希清单保持原样。
