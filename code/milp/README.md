# 多线选择性拆卸 MILP

实现 `problem/main.tex` 中的基准模型 P0，使用 PuLP 建模和 CBC 求解。所有示例均为合成数据，不代表生理安全标准。仅实现原始 MILP；列生成留待后续研究。

## 运行

在项目根目录运行（Python 3.10 及以上）：

```powershell
python -m pip install -r code/milp/requirements.txt
python code/milp/model.py code/milp/examples/single_line.json --output code/milp/results/single_line.json
python code/milp/model.py code/milp/examples/two_lines.json --output code/milp/results/two_lines.json --lp code/milp/results/two_lines.lp
python -m unittest discover -s code/milp -p test_model.py -v
```

可选 `--time-limit 60`（秒）、`--gap 0.01`（相对 gap）、`--verbose`（CBC 日志）。默认 gap 为 0。PuLP 的常见二进制发行包附带 CBC；若环境无 CBC，需安装包含 CBC 的发行包。也可以调用 `build_model(data)`，通过返回对象的 `problem.solve(...)` 接入其他 PuLP 求解器，再调用 `solution_report(model)` 读取结果。

## 数据格式与数学符号

| JSON 字段 | 数学符号／含义 |
|---|---|
| `human_limit`, `robot_limit` | 全系统 Hmax、Rmax，非负整数 |
| `lines` | 线列表；只提供一条线即 L=1 |
| 线的 `id` | 非空且唯一的字符串标识 |
| `cycle_time` | T，正数 |
| `fatigue_limit` | Fmax，0 ≤ Fmax < 1 |
| `min_recovery` | Q，可省略，默认 0 |
| `stations` | 按工艺顺序排列的非空站点列表，站号从 1 开始 |
| 站点的 `fixed_cost`, `human_cost`, `robot_cost` | f、fH、fR，均非负 |
| `tasks` | 非空任务列表；任务标识在线内唯一，可跨线重用 |
| 任务的 `id`, `value`, `weight` | 标识、v、w；weight 可省略，默认 0 |
| 任务的 `modes` | 仅列出允许的 H/R/J 模式，至少一种 |
| 模式的 `time`, `cost`, `beta` | t > 0、c ≥ 0、β ≥ 0；R 模式 β 必须为 0 |
| `precedence` | `[前驱任务ID, 后继任务ID]` 列表，可省略；必须为 DAG |
| `required_tasks` | 必拆任务 ID 列表，可省略，默认空集 |

`value` 可以为负；所有数值必须有限。疲劳量由 d=βt 计算，不另输入 d，以避免两套参数不一致；阈值由 B=-log1p(-Fmax) 预计算。所有模式均无不同任务并行，J 模式只计一次持续时间。站点数 K 取 `stations` 长度，n 取 `tasks` 长度，不需要重复填写。

任务和线 ID 使用字符串（例如 `"1"`），输入标识不会直接拼到求解器变量名，因此不会因标点清洗造成重名。未知字段会报错以发现拼写错误。输入验证只检查数据定义；如必拆任务用时超过节拍、最低回收要求不可达到等数学不可行情形，由求解器报告。

## 输出及模型对应

`status` 和 `solution_status` 保留 PuLP 的状态；`has_feasible_solution` 还检查变量边界、整数性及约束可行性（容差 1e-6）。只有存在通过检查的整数解时才输出利润、任务与站点安排。时间限制下可行解不等于已证明最优解；设置正 gap 时 `optimal` 保守地返回 false。无可行解时 `objective` 为 null，进程退出码为 2；输入或执行错误退出码为 1。

`profit_breakdown` 输出回收收益、执行成本、站点成本、工人成本、机器人成本。每个工作站输出启用和配置状态、按拓扑顺序排列的任务和模式、时间、累积疲劳量 D、疲劳水平 F 和负荷阈值 B。未启用站点也会输出，便于检查站点间空缺。输出不包含任务开始时间；在本模型的串行、无恢复假设下，拓扑顺序足以给出站内合法执行次序。

代码约束名称 `eq06_*` 至 `eq18_*` 对应文档公式，变量通过 `cat="Binary"` 实现式 (19)。式 (9)–(11) 的双边逻辑分别写成两个线性不等式。不存在默认的连续启用站点约束，异质站点可以保留空缺。无需配置的资源禁止空配，即使配置成本为零也保持等价逻辑。

测试通过独立枚举任务选择、站点和模式，直接计算原始指数疲劳并比较最优净利润，覆盖单线、多线、资源紧张及不可行情形；同时检查同站先后、反向跨站、J 时间、疲劳零阈值和异质站点。

疲劳仅表示代表性单周期、从零初始疲劳开始的累积，不包含整班次、恢复或对时间的反馈。成本与回收价值需使用同一核算口径，避免重复扣费。
