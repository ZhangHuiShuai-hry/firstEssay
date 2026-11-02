# RMP、对偶、定价与两阶段推导

使用 MATHEMATICAL_AUDIT 中的完整主问题；RMP 将每块 $\mathcal P_{ls}$ 换成受限子集，变量非负且无显式 LP 上界。每块有空列，局部集合有限且有界，不存在待定价的极射线。

## 1. 对偶

最大化 $\max\{c^T\lambda:A_\le\lambda\le b_\le,A_=\lambda=b_=,\lambda\ge0\}$ 的对偶是 $\min b^T\pi$，满足 $A^T\pi\ge c$；$\le$ 行的 π 非负，等式行自由。

| 变量 | 对应主问题约束 | 符号 | 定价贡献 | 实现 |
|---|---|---|---|---|
| $\alpha_{ls}$ | 凸性 $\sum_p\lambda=1$ | 自由 | $-\alpha_{ls}$ | `pricing.py:47`；`common.py:128` |
| $\pi_{li}$（可选） | 覆盖 $\sum a\lambda\le1$ | $\ge0$ | $-\pi_{li}a_{ip}$ | `master.py:37`；`pricing.py:31` |
| $\pi_{li}$（必拆） | 覆盖 $\sum a\lambda=1$ | 自由 | 同上；没有另一份必拆对偶 | `master.py:38`；`pricing.py:31` |
| $\mu_{lijk}$ | 前缀后继减前驱 $\le0$ | $\ge0$ | $-\sum_{k\ge s}\mu_{lijk}(a_{jp}-a_{ip})$ | `common.py:132`；`pricing.py:19` |
| $\theta_l$ | 负回收 $-\sum q\lambda\le-Q_l$ | $\ge0$ | $+\theta_lq_p$ | `master.py:42`；`pricing.py:31` |
| $\eta_H$ | 全局人工 | $\ge0$ | $-\eta_H H_p$ | `pricing.py:45` |
| $\eta_R$ | 全局机器人 | $\ge0$ | $-\eta_R R_p$ | `pricing.py:46` |

上述各项 PASS。必拆与可选任务是同一类行的不同 sense，不能另叠加一个“必拆价格”重复扣除。疲劳在列内，没有主问题疲劳对偶。

对偶目标为

$$D(\alpha,\pi,\mu,\theta,\eta)=\sum_{ls}\alpha_{ls}+\sum_{li}\pi_{li}+H^{max}\eta_H+R^{max}\eta_R-\sum_lQ_l\theta_l.$$

对每列的对偶不等式是

$$\alpha_{ls}+\sum_i\pi_{li}a_{ip}+\sum_{(i,j)\in E_l}\sum_{k=s}^{K_l}\mu_{lijk}(a_{jp}-a_{ip})+\eta_HH_p+\eta_RR_p-\theta_lq_p\ge b_{lsp}.$$

RMP 对偶仅要求已有列的不等式，完整对偶要求全部列。

## 2. 前缀贡献与检验数

站 s 的列出现在且只出现在 k≥s 的前缀行。该列在边 (i,j)、前缀 k 的系数为 $(a_{jp}-a_{ip})1_{s\le k}$。所以

$$\bar c_{lsp}=b_{lsp}-\alpha_{ls}-\sum_i\pi_{li}a_{ip}-\sum_{(i,j)}\sum_{k=s}^{K_l}\mu_{lijk}(a_{jp}-a_{ip})-\eta_HH_p-\eta_RR_p+\theta_lq_p.$$

对某任务 i，把出边和入边分组：

$$\sigma_{li}^s=\sum_{j:(i,j)\in E_l}\sum_{k=s}^{K_l}\mu_{lijk}-\sum_{j:(j,i)\in E_l}\sum_{k=s}^{K_l}\mu_{ljik}.$$

前驱取正调整，后继取负调整。这来自 $c-A^T\pi$，不是凭求解器对偶显示的直觉选择符号。`common.py:125` 直接生成稀疏行向量，`pricing.py:19` 和 `persistent_pricing.py:59` 使用调整收益；三种计算路径已与独立行向量、两阶段任意对偶和全部列比较。

## 3. 定价问题

每个 $(l,s)$ 使用二进制 $z_{im},u,h,r$，最大化

$$\sum_{im}(v_{li}-c_{li}^m-\pi_{li}+\theta_lw_{li}+\sigma_{li}^s)z_{im}-f_{ls}u-(f^H_{ls}+\eta_H)h-(f^R_{ls}+\eta_R)r-\alpha_{ls}.$$

局部约束完整为

\[
\begin{aligned}
\sum_mz_{im}&\le1 &&(i),\\
\sum_{im}t_{li}^mz_{im}&\le T_lu,\\
u\le\sum_{im}z_{im}&\le n_lu,\\
h\le\sum_{im}a_m^Hz_{im}&\le n_lh,\\
r\le\sum_{im}a_m^Rz_{im}&\le n_lr,\\
\sum_{im}d_{li}^mz_{im}&\le B_lh,\\
z,u,h,r&\in\{0,1\}.
\end{aligned}
\]

不加必拆、回收、全局人机上限或前驱闭包；所有这些耦合通过对偶体现。同站 AND 顺序通过诱导 DAG 的拓扑序实现。空列永远可行，因此“PP 已证不可行”在当前模型下是异常，不是正常的无改进终止。

由局部可行整数点与列一一对应，定价最优值恰为 $\rho_{ls}=\max_{p\in\mathcal P_{ls}}\bar c_{lsp}$。最大化中 $\rho>\varepsilon$ 加列；$\rho\le\varepsilon$ 才能该块判停。`blocks` 双重循环覆盖所有线和所有站，没有只检查已启用站。空站也必须定价。

## 4. Phase I

必拆行加 $q_{li}^{req}\ge0$：$\sum a\lambda+q^{req}=1$；回收行加 $q_l^{rec}\ge0$：$-\sum q_p\lambda-q^{rec}\le-Q_l$。目标 $\max(-\sum q^{req}-\sum q^{rec})$，真实列成本全部为零。空列令所有优先/资源行可行，人工变量补足必拆和回收，因此初始 Phase I RMP 一定可行且目标≤0。

真实列的 Phase I 检验数把上面 PP 的 $v-c,f,f^H,f^R$ 全部置零，仍使用**本阶段新求的**对偶。人工变量还产生对偶约束 $\pi_{li}^{req}\ge-1$、$\theta_l\le1$；其他符号照旧。

人工总量归零时，真实列支持完整列 LP 的可行解，可不继续定价直接切 Phase II。数值上代码用 `feasibility_tolerance=1e-7` 判断；若残差实际使 Phase II RMP 不可行，会中止并保留错误证据，不能把这一切换解释为精确有理证明。

若完整定价无正改进且修复对偶上界仍 $UB_I<-feasibility\_tolerance$，完整 Phase I 最优值严格负，故 Full-LP 不可行、原 IP 也不可行。若界未严格负，报告数值不确定。仅“人工变量仍正”不能证明不可行，迭代截断也不能证明不可行。

重建 RMP 切阶段会移除人工变量并恢复利润；增量 RMP 把人工上界固定为0、人工系数置0、已有及新增列恢复利润。持久 PP 对每个变量重写目标，并单独重写凸性常数，未复用旧阶段价格。

## 5. Phase II 与终止

每次 RMP 必须已证 LP 最优、原始可行，所有对偶有限且符号符合行 sense。检查已有列 $c-A^T\pi$ 与求解器 dj 一致。每块求 PP 已证最优；时间截断、有 incumbent、最优容差状态、未知状态或异常不能代替已证最优。

所有块完成且 $\max\rho\le\varepsilon$ 才是根 Full-LP 在容差意义下的证明。精确零检验数时强对偶得到 $Z_{RMP}=Z_{Full-LP}$。数值终止的**全局绝对差距上限是 $|B|\varepsilon$**，其中 $|B|=\sum_lK_l$，不是必然≤ε；实际使用逐块修复计算 UB，不直接抹成 RMP 值。退化时加正检验数列不保证本轮利润严格增加。

## 6. 有效上界定理及限制

设当前 RMP 对偶 π 符号正确，并对已有列对偶可行；$D=b^T\pi$。每块都有真实、有效的最大化定价上界 $\widehat\rho_{ls}\ge\rho_{ls}$。令 $\delta_{ls}=\max(0,\widehat\rho_{ls})$，只将自由凸性对偶更新为 $\alpha'_{ls}=\alpha_{ls}+\delta_{ls}$。每列恰属于一个块且该块凸性系数为1，因此

$$\bar c'_{lsp}=\bar c_{lsp}-\delta_{ls}\le\rho_{ls}-\delta_{ls}\le0.$$

π′ 对所有完整列对偶可行，弱对偶给出

$$Z_{Full-LP}\le D+\sum_{ls}\max(0,\widehat\rho_{ls}).$$

若 RMP 已证最优且强对偶成立，$D=Z_{RMP}$，即题设的公式。没有最优 RMP 时不能直接用 RMP incumbent 替代 D。若凸性 RHS 为 $b_{ls}$ 应加 $\sum b_{ls}\delta_{ls}$；本项目 RHS 全为1。对偶负号/数据缺失不能靠该修复修正；修复仅改变凸性 α。

使用条件：完整覆盖全部块；每个上界针对同一轮、同一对偶和同一阶段；包括 $-\alpha_{ls}$ 常数；不是启发式 incumbent；符号及对偶残差在记录容差内；日志截断/打印舍入需外向保守处理。Phase I 同样适用，但它的界是人工目标界，不能作为利润上界。

当前 CG 只接受已证最优 PP，公式中的输入是精确求解所得的最大检验数，不是截断 PP 的 Best Bound。持久 PP 虽记录截断 bound，当前控制流仍抛错，**尚未实现用不完整精确定价的 bound 继续 CG 或生成新轮上界**。不能把记录字段存在理解为该扩展已经实现。

独立程序逐轮重算 $D$、全部列最大检验数、修复后每列对偶不等式，并比较真实 Full-LP；新增回归另外覆盖目标常数和 CBC 打印界。整个证书是求解器容差下的数值证明，不是精确有理证书。
