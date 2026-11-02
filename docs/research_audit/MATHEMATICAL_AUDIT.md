# 数学模型审计

审计日期：2026-11-02。以本地提交 `2a1f76c` 的 `problem/main.tex`、`problem/dwcg/main.tex` 和实际代码为准。本次不改变物理假设、目标或约束。数学证明在精确实数算术下成立，计算验证采用显式浮点容差。

## 1. 紧凑模型的规范形式

集合：拆卸线 $l\in\mathcal L$；线内任务 $i\in I_l$，$n_l=|I_l|$；有序候选站 $s\in S_l=\{1,\ldots,K_l\}$；AND DAG 边 $(i,j)\in E_l$；允许模式 $m\in M_{li}\subseteq\{H,R,J\}$；必拆任务 $I_l^{req}$。任务 ID 仅在线内唯一。

参数：价值 $v_{li}\in\mathbb R$；模式时间 $t_{li}^m>0$、直接成本 $c_{li}^m\ge0$、疲劳系数 $\beta_{li}^m\ge0$，其中 $\beta^R=0$；权重 $w_{li}\ge0$；节拍 $T_l>0$；疲劳阈值 $0\le F_l^{max}<1$；最低回收 $Q_l\ge0$；站费 $f_{ls}\ge0$、配置费 $f^H_{ls},f^R_{ls}\ge0$；系统资源整数上限 $H^{max},R^{max}\ge0$。定义 $d_{li}^m=t_{li}^m\beta_{li}^m$，$B_l=-\log(1-F_l^{max})$。模式资源指示 $a^H_H=a^H_J=1,a^H_R=0$；$a^R_R=a^R_J=1,a^R_H=0$。

二进制变量：选择 $y_{li}$；分配与模式 $x_{lism}$；启用 $u_{ls}$；人工 $h_{ls}$；机器人 $r_{ls}$。仅允许模式建立变量，不另设“模式选择变量”。记

$$N_{ls}=\sum_{i,m}x_{lism},\quad N^H_{ls}=\sum_{i,m}a^H_mx_{lism},\quad N^R_{ls}=\sum_{i,m}a^R_mx_{lism}.$$

目标：

$$\max\sum_{li}v_{li}y_{li}-\sum_{lism}c_{li}^mx_{lism}-\sum_{ls}(f_{ls}u_{ls}+f^H_{ls}h_{ls}+f^R_{ls}r_{ls}).$$

完整约束：

\[
\begin{aligned}
\sum_{s,m}x_{lism}&=y_{li} &&(l,i),\\
\sum_{s\le k,m}x_{ljsm}-\sum_{s\le k,m}x_{lism}&\le0 &&(l,(i,j)\in E_l,k\in S_l),\\
\sum_{i,m}t_{li}^mx_{lism}&\le T_lu_{ls} &&(l,s),\\
u_{ls}\le N_{ls}&\le n_lu_{ls} &&(l,s),\\
h_{ls}\le N^H_{ls}&\le n_lh_{ls} &&(l,s),\\
r_{ls}\le N^R_{ls}&\le n_lr_{ls} &&(l,s),\\
\sum_{i,m}d_{li}^mx_{lism}&\le B_lh_{ls} &&(l,s),\\
\sum_{ls}h_{ls}&\le H^{max},\\
\sum_{ls}r_{ls}&\le R^{max},\\
y_{li}&=1 &&(l,i\in I_l^{req}),\\
\sum_i w_{li}y_{li}&\ge Q_l &&(l),\\
x,y,u,h,r&\in\{0,1\}. 
\end{aligned}
\]

没有站点连续启用约束，没有人工/机器人跨站实时移动，没有并行任务，没有整班次恢复模型。J 时间只计一次。配置逻辑的双向不等式强制“有使用才配置且使用必配置”，即使配置费为零也成立。空站必为 $u=h=r=0$。非空站允许前面有空站，异质站费时这一点不可删去。

疲劳说明：$F=1-e^{-D}$ 单调递增，$F\le F^{max}$ 等价 $D\le B_l$。$h=1$ 时直接成立；$h=0$ 时配置逻辑只允许 R，且 $d^R=0$，故 $D\le B_lh$ 对整数模型精确。这里只是代表性单周期的累计疲劳，不能外推整班次生理有效性。

## 2. 公式与实现逐项对照

下列行号对应本次交付版本；紧凑数学构造函数未修改。路径相对仓库根目录。

| 数学约束/定义 | 数学表达式 | Python 实现位置 | 检查结果 |
|---|---|---|---|
| 数据域及有限数 | 上述参数域、DAG、允许模式 | `code/milp/model.py:83` validate_data | PASS |
| 疲劳参数 | $d=\beta t,B=-\log(1-F)$ | `code/milp/model.py:170`、`:204` | PASS |
| 利润 | 价值减直接、站、人、机成本 | `code/milp/model.py:215` profit_terms | PASS |
| 唯一分配/模式 | $\sum_{s,m}x=y$ | `code/milp/model.py:180` | PASS |
| 必拆 | $y=1$ | `code/milp/model.py:182` | PASS |
| 累积 AND | 每边每前缀后继减前驱 $\le0$ | `code/milp/model.py:205` | PASS |
| 节拍 | $\sum tx\le Tu$ | `code/milp/model.py:196` | PASS |
| 启用 | $u\le N\le nu$ | `code/milp/model.py:198` eq09 | PASS |
| 人工配置 | $h\le N^H\le nh$ | `code/milp/model.py:199` eq10 | PASS |
| 机器人配置 | $r\le N^R\le nr$ | `code/milp/model.py:200` eq11 | PASS |
| 疲劳 | $\sum dx\le Bh$ | `code/milp/model.py:203` | PASS |
| 全局人工 | $\sum h\le H^{max}$ | `code/milp/model.py:213` | PASS |
| 全局机器人 | $\sum r\le R^{max}$ | `code/milp/model.py:214` | PASS |
| 回收 | $\sum wy\ge Q$ | `code/milp/model.py:211` | PASS |
| 二进制域 | $x,y,u,h,r\in\{0,1\}$ | `code/milp/model.py:174`、`:178`、`:185` | PASS |
| 解的实际顺序 | 站内诱导 DAG 拓扑排序 | `code/milp/model.py:59`、`:244` | PASS |

## 3. 列与局部/全局边界

固定 $(l,s)$，定义有限集合 $X_{ls}$：二进制 $z_{im},U,H,R$ 满足每任务 $\sum_mz_{im}\le1$、节拍、三个配置双向逻辑及疲劳，与紧凑模型对应局部约束完全相同。$\mathcal P_{ls}$ 枚举 $X_{ls}$ 的每一个整数配置。每任务局部上限在紧凑模型中由全局分配和非负性隐含，因此加入局部定义是合法的。

列属性：任务模式 $(i,m)$ 元组；$a_{ip}=\sum_m z_{im}^p$；$U_p,H_p,R_p$；用时 $\tau_p=\sum tz$；负荷 $D_p=\sum dz$；回收 $q_p=\sum_iw_ia_{ip}$；利润

$$b_{lsp}=\sum_{im}(v_{li}-c_{li}^m)z_{im}^p-f_{ls}U_p-f^H_{ls}H_p-f^R_{ls}R_p.$$

生产 Column 直接存 profit，不分别存收益/直接成本/配置费，但均能由 assignments 和原始输入唯一重算。空列为全零，利润为零。不同站费使相同 assignments 的 profit 依站变化。

局部：模式、每任务至多一次、站内节拍、疲劳、启用和配置逻辑。全局：任务跨站唯一、必拆、各边各前缀优先、回收、跨线人机资源。局部不要求前驱闭包，也不施加全系统人机资源上限。站内 DAG 拓扑排序总存在，列可以只有后继而前驱在早站。把前驱闭包或全局资源限制加入 PP 会改变分解；当前代码没有这样做。

`common.py:64` 实现局部构造；`:98` 枚举但复用局部构造，不能独自排除共同错误。本次 `independent_validation.py` 独立枚举及算术实现作为第二条证据链。

## 4. 完整列模型

用 $\lambda_{lsp}$ 表示选列，目标 $\max\sum b_{lsp}\lambda_{lsp}$。约束：

\[
\begin{aligned}
\sum_p\lambda_{lsp}&=1 &&(l,s),\\
\sum_{sp}a_{ip}\lambda_{lsp}&\le1 &&(l,i\notin I_l^{req}),\\
\sum_{sp}a_{ip}\lambda_{lsp}&=1 &&(l,i\in I_l^{req}),\\
\sum_{s\le k,p}(a_{jp}-a_{ip})\lambda_{lsp}&\le0 &&(l,(i,j),k),\\
\sum_{lsp}H_p\lambda_{lsp}&\le H^{max},\quad\sum_{lsp}R_p\lambda_{lsp}\le R^{max},\\
-\sum_{sp}q_p\lambda_{lsp}&\le-Q_l &&(l).
\end{aligned}
\]

Full-IP：$\lambda\in\{0,1\}$；Full-LP：$\lambda\ge0$。凸性已隐含上界1，不另设 LP 变量上界。RMP 仅将每块列集合限制为已有子集，其他行不变。实现为 `master.py:28`。

## 5. 整数等价性的双向证明

**紧凑整数解到完整列 IP。** 给定紧凑可行整数解。每站提取 $z_{im}=x_{lism}$。由 $\sum_{sm}x=y\le1$ 得该站每任务至多一个模式。节拍、疲劳及三个配置逻辑正是 $X_{ls}$ 约束，故提取的配置必在完整 $\mathcal P_{ls}$ 中。配置逻辑还使 U/H/R 与原 u/h/r 完全一致，包括空站（只能全零）。选该列 $\lambda=1$，其余为0，满足凸性。

任务列系数之和等于原 $y$，所以可选不重复、必拆仍为1。每前缀列系数之和严格等于原前缀 $x_j-x_i$ 之和，优先关系保留；人工/机器人系数之和等于原配置总数，回收和原 $\sum wy$ 相同。将列利润展开，任务收益借助 $y=\sum x$ 完全相同，执行成本和配置成本逐项相同，目标不变。原解有异质空缺站也仍可逐站选空列，不需移动任务。

**完整列整数解到紧凑模型。** 每站非负二进制 λ 之和为1，故恰选一列。定义

$$x_{lism}=\sum_pz_{im}^p\lambda_{lsp},\quad(u,h,r)_{ls}=\sum_p(U,H,R)_p\lambda_{lsp},\quad y_{li}=\sum_{sp}a_{ip}\lambda_{lsp}.$$

每站的 x/u/h/r 唯一确定且为二进制。任务覆盖行和局部每任务上限保证跨站不重复，因此 y 为0/1，分配等式成立，必拆 y=1。每站所选列保证所有局部约束；主问题优先、资源、回收行经上述代换分别得到原约束。DAG 在各站内可拓扑排序，不需要额外序列变量。目标展开完全相同。

如果列池存在重复 assignments，λ 的表示可以不唯一，但对于给定选列解恢复出的原变量仍唯一；不影响目标或等价结论。生产 CG 按排序元组去重，完整枚举亦无重复。

两个映射保留可行性及利润，因此包括双方不可行的情形（最大化不可行值可约定为 $-\infty$）：

$$\boxed{Z_{Compact-IP}=Z_{Full-DW-IP}.}$$

此结论只对**完整**列集成立，不适用于生成列池上的受限 IP。它不依赖成本严格为正，也不依赖全部任务必须执行。

## 6. LP 松弛关系与严格性的证据

Full-LP 每块投影属于 $\operatorname{conv}(X_{ls})$。局部整数点满足紧凑所有局部线性不等式及0/1界，凸组合也满足；全局行在映射下完全一致。因此 Full-LP 投影包含于 Compact-LP 可行域。Full-IP 的整数点属于 Full-LP，得到

$$Z_{Compact-IP}=Z_{Full-IP}\le Z_{Full-LP}\le Z_{Compact-LP}.$$

一般不存在反向包含：紧凑大 M 配置约束允许分数配置支付分数成本，时间/疲劳背包线性松弛也未必为整数凸包。给出可复现实例证据：single_line 的 Full-LP=21，Compact-LP≈22.239912；two_lines 的 Full-LP=27，Compact-LP≈36.701635（以 VALIDATION_REPORT 的实际数值为准）。故两种 LP 相等的普遍命题被明确反例否定。

相等的充分条件是所有全局可行紧凑 LP 点的每块均能表示成 $X_{ls}$ 的凸组合；局部线性多面体恰为整数凸包是更强的充分条件。没有证明本项目具备该性质。Full-LP 不可行但 Compact-LP 可行并不矛盾。Phase I 的 LP 可行也不意味着 IP 可行，独立测试构造了反例。

## 7. 结论边界

PASS：文档、紧凑整数模型和完整整数列模型的数学一致性及上述证明。PASS：有限小规模独立枚举支持这一结论。不能从小规模测试推断任意浮点病态输入均可靠，也不能把模型内部一致性解释为生理疲劳参数的外部实证有效性。
