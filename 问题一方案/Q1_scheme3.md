# 问题一：静态环境下城市绿色物流配送调度模型（多趟修正版）

## 1. 问题重述

在无政策限制条件下，需要为某物流企业设计静态配送方案。配送任务涉及 98 个客户点，需求由 2169 个订单构成。车辆为异构混合车队，且同时受到重量容量、体积容量、软时间窗、时变速度、能耗成本与碳排放成本的影响。

结合订单数据的实际结构，问题一应采用如下建模口径：

- **订单不可拆分**：每个订单必须完整地由某一辆车在某一趟任务中配送；
- **客户可拆可不拆**：同一客户的多个订单可以由一辆车一次完成，也可以由多辆车分次完成；
- **单车允许多趟**：同一辆物理车辆完成一趟任务返回配送中心后，允许重新装载并再次出发。

因此，问题一可建模为一个：

$$
\text{订单不可拆分、客户可分次服务、异构车队、多趟、双容量约束、软时间窗、时变速度的绿色车辆路径优化模型}
$$

---

## 2. 模型假设

1. 原始数据以订单为基本单位，每个订单仅对应一个客户点，且单个订单不可拆分。
2. 路径节点以客户点表示，同一客户点可对应多个订单。
3. 对于需求较小的客户，其全部订单可由一辆车在一趟任务中完成；对于需求较大的客户，允许由多辆车或同一车辆的不同趟次共同完成配送。
4. 是否对某客户进行拆分服务，不预先设定，而由优化模型根据容量、时间窗与成本自动决定。
5. 所有车辆均从配送中心出发，每一趟任务结束后返回配送中心；同一车辆在同一计划日内可执行多趟任务。
6. 每辆车在同一趟任务中对同一客户至多访问一次；不同趟次之间允许再次访问同一客户。
7. 每次车辆到访客户均需发生一次服务作业，服务时间固定为 20 分钟。
8. 车辆速度受交通时段影响，静态优化中采用各时段速度分布均值构造时变旅行时间函数。
9. 软时间窗对每一次客户到访均生效；提前到达产生等待成本，延迟到达产生惩罚成本。
10. 车辆能耗由车速与载荷率共同决定，并进一步折算为能耗成本与碳排放成本。
11. 车辆每次返回配送中心后，重新装载需要消耗固定周转时间。????????????????????????????????????????
12. 规划周期内每辆车的最大趟次数设置为一个足够大的上界 $P_{\max}$，由数据预处理或算法阶段给定。

---

## 3. 符号说明

## 3.1 集合与索引

- $C=\{1,2,\dots,n\}$：客户集合；
- $N=\{0\}\cup C$：节点集合，其中 $0$ 表示配送中心；
- $R$：订单集合；
- $R_i\subseteq R$：客户 $i$ 的订单集合；
- $K$：车辆集合；
- $H$：车型集合；
- $K_h\subseteq K$：车型 $h$ 对应的车辆集合；
- $K^F\subseteq K$：燃油车集合；
- $K^E\subseteq K$：新能源车集合；
- $P=\{1,2,\dots,P_{\max}\}$：单车可执行的趟次集合；
- $A=\{(i,j)\mid i,j\in N,\ i\neq j\}$：可行弧集合。

索引说明：

- $i,j,h$：节点索引；
- $r$：订单索引；
- $k$：车辆索引；
- $m$：车型索引；
- $p$：趟次索引。

---

## 3.2 参数定义

### （1）订单参数

- $w_r$：订单 $r$ 的重量（kg）；
- $v_r$：订单 $r$ 的体积（m$^3$）；
- $i(r)$：订单 $r$ 所属客户编号。

### （2）客户参数

- $[a_i,b_i]$：客户 $i$ 的软时间窗；
- $s_i$：客户 $i$ 的服务时间，题中取 $20$ 分钟，即 $\frac{1}{3}$ 小时。

客户 $i$ 的聚合需求定义为：

$$
q_i=\sum_{r\in R_i} w_r
$$

$$
u_i=\sum_{r\in R_i} v_r
$$

注意：$q_i,u_i$ 仅表示客户总需求统计量，并不意味着客户需求可以连续拆分。

### （3）车辆参数

- $Q_k$：车辆 $k$ 的最大载重（kg）；
- $U_k$：车辆 $k$ 的最大容积（m$^3$）；
- $F_k$：车辆 $k$ 的固定启用成本（元）；
- $n_m$：车型 $m$ 的可用车辆数；
- $\rho_k$：车辆 $k$ 每次返回配送中心后的重新装载准备时间（h）。

### （4）路网与时间参数

- $d_{ij}$：节点 $i$ 到节点 $j$ 的道路距离（km）；
- $\bar v(t)$：时刻 $t$ 对应的平均速度（km/h）；
- $\tau_{ij}(t)$：车辆在时刻 $t$ 从节点 $i$ 出发到达节点 $j$ 的旅行时间（h）；
- $t_0$：计划期开始时刻；
- $B$：足够大的正常数（Big-M 常数）。

### （5）成本参数

- $c_w=20$：单位等待成本（元/h）；
- $c_l=50$：单位迟到惩罚成本（元/h）；
- $p^F=7.61$：燃油价格（元/L）；
- $p^E=1.64$：电价（元/(kW$\cdot$h)）；
- $p^C=0.65$：单位碳排放成本（元/kg）。

### （6）能耗与碳排放参数

燃油车百公里油耗函数：

$$
FPK(v)=0.0025v^2-0.2554v+31.75
$$

新能源车百公里电耗函数：

$$
EPK(v)=0.0014v^2-0.12v+36.19
$$

满载附加系数：

- 燃油车：$0.4$；
- 新能源车：$0.35$。

碳排放系数：

- 燃油车：$\eta=2.547$ kg/L；
- 新能源车：$\gamma=0.501$ kg/(kW$\cdot$h)。

---

## 4. 时变速度函数

根据题意，采用各时段速度分布均值构造平均速度函数：

$$
\bar v(t)=
\begin{cases}
9.8, & t\in [8{:}00,9{:}00)\cup[11{:}30,13{:}00) \\
35.4, & t\in [10{:}00,11{:}30)\cup[15{:}00,17{:}00) \\
55.3, & t\in [9{:}00,10{:}00)\cup[13{:}00,15{:}00)
\end{cases}
$$

对应地，定义时变旅行时间函数：

$$
\tau_{ij}(t)=\text{车辆在时刻 }t\text{ 从节点 }i\text{ 出发到达节点 }j\text{ 所需的旅行时间}
$$

若车辆跨越多个交通时段，则采用分段累计法计算总旅行时间。

---

## 5. 决策变量

### 5.1 订单分配变量

$$
\alpha_{rkp}=
\begin{cases}
1, & \text{若订单 }r\text{ 由车辆 }k\text{ 的第 }p\text{ 趟承运} \\
0, & \text{否则}
\end{cases}
\qquad \forall r\in R,\ \forall k\in K,\ \forall p\in P
$$

该变量用于保证订单不可拆分。

### 5.2 客户—车辆—趟次服务变量

$$
\delta_{ikp}=
\begin{cases}
1, & \text{若车辆 }k\text{ 在第 }p\text{ 趟到访并服务客户 }i \\
0, & \text{否则}
\end{cases}
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

### 5.3 路径变量

$$
x_{ijkp}=
\begin{cases}
1, & \text{若车辆 }k\text{ 在第 }p\text{ 趟从节点 }i\text{ 行驶到节点 }j \\
0, & \text{否则}
\end{cases}
\qquad \forall (i,j)\in A,\ \forall k\in K,\ \forall p\in P
$$

### 5.4 趟次启用变量

$$
z_{kp}=
\begin{cases}
1, & \text{若车辆 }k\text{ 执行第 }p\text{ 趟任务} \\
0, & \text{否则}
\end{cases}
\qquad \forall k\in K,\ \forall p\in P
$$

### 5.5 车辆启用变量

$$
y_k=
\begin{cases}
1, & \text{若车辆 }k\text{ 在计划期内被启用} \\
0, & \text{否则}
\end{cases}
\qquad \forall k\in K
$$

### 5.6 弧载荷变量

- $f_{ijkp}$：车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上承载的重量载荷（kg）；
- $g_{ijkp}$：车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上承载的体积载荷（m$^3$）。

### 5.7 时间变量

- $A_{ikp}$：车辆 $k$ 在第 $p$ 趟到达客户 $i$ 的时刻；
- $W_{ikp}$：车辆 $k$ 在第 $p$ 趟于客户 $i$ 的等待时间；
- $L_{ikp}$：车辆 $k$ 在第 $p$ 趟于客户 $i$ 的迟到时间；
- $T_{kp}^{\mathrm{dep}}$：车辆 $k$ 第 $p$ 趟从配送中心出发时刻；
- $T_{kp}^{\mathrm{ret}}$：车辆 $k$ 第 $p$ 趟返回配送中心时刻。

定义车辆在客户 $i$ 完成服务后的离开时刻为：

$$
D_{ikp}=A_{ikp}+W_{ikp}+s_i
$$

---

## 6. 目标函数

问题一以总配送成本最小为目标，总成本由以下五部分构成：

1. 车辆固定启用成本；
2. 能耗成本；
3. 碳排放成本；
4. 提前到达等待成本；
5. 迟到惩罚成本。

因此目标函数为：

$$
\min Z=C_{\text{fix}}+C_{\text{ene}}+C_{\text{car}}+C_{\text{wait}}+C_{\text{late}}
$$

### 6.1 固定启用成本

$$
C_{\text{fix}}=\sum_{k\in K}F_k y_k
$$

### 6.2 弧上载荷率

定义车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上的重量载荷率为：

$$
\lambda_{ijkp}=\frac{f_{ijkp}}{Q_k}
$$

### 6.3 弧出发时刻

定义车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上的出发时刻为：

$$
\theta_{ijkp}=
\begin{cases}
T_{kp}^{\mathrm{dep}}, & i=0 \\
A_{ikp}+W_{ikp}+s_i, & i\in C
\end{cases}
$$

### 6.4 燃油车弧上油耗量

若 $k\in K^F$，则弧 $(i,j)$ 上的油耗量为：

$$
\phi_{ijkp}^{F}
=
\frac{d_{ij}}{100}
\cdot
FPK\bigl(\bar v(\theta_{ijkp})\bigr)
\cdot
\left(1+0.4\lambda_{ijkp}\right)
$$

### 6.5 新能源车弧上电耗量

若 $k\in K^E$，则弧 $(i,j)$ 上的电耗量为：

$$
\phi_{ijkp}^{E}
=
\frac{d_{ij}}{100}
\cdot
EPK\bigl(\bar v(\theta_{ijkp})\bigr)
\cdot
\left(1+0.35\lambda_{ijkp}\right)
$$

### 6.6 能耗成本

$$
C_{\text{ene}}
=
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^F\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^E\phi_{ijkp}^{E}
$$

### 6.7 碳排放成本

$$
C_{\text{car}}
=
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^C\eta\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^C\gamma\phi_{ijkp}^{E}
$$

### 6.8 等待成本

$$
C_{\text{wait}}=c_w\sum_{i\in C}\sum_{k\in K}\sum_{p\in P} W_{ikp}
$$

### 6.9 迟到惩罚成本

$$
C_{\text{late}}=c_l\sum_{i\in C}\sum_{k\in K}\sum_{p\in P} L_{ikp}
$$

---

## 7. 约束条件

## 7.1 订单唯一分配约束

每个订单必须且只能由一辆车的某一趟任务承运：

$$
\sum_{k\in K}\sum_{p\in P}\alpha_{rkp}=1,
\qquad \forall r\in R
$$

该约束直接保证订单不可拆分。

---

## 7.2 订单分配与客户服务联动约束

若订单 $r$ 由车辆 $k$ 的第 $p$ 趟承运，则该趟必须服务订单所属客户：

$$
\alpha_{rkp}\le \delta_{i(r)kp},
\qquad \forall r\in R,\ \forall k\in K,\ \forall p\in P
$$

反向约束为：

$$
\delta_{ikp}\le \sum_{r\in R_i}\alpha_{rkp},
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

因此，$\delta_{ikp}=1$ 当且仅当车辆 $k$ 的第 $p$ 趟至少承运客户 $i$ 的一个订单。

---

## 7.3 客户服务完整性约束

每个客户至少被一次服务：

$$
\sum_{k\in K}\sum_{p\in P}\delta_{ikp}\ge 1,
\qquad \forall i\in C
$$

该约束体现客户既可单次服务，也可多次分次服务。

---

## 7.4 趟次启用与车辆启用联动约束

若车辆 $k$ 执行第 $p$ 趟，则车辆 $k$ 必须被启用：

$$
z_{kp}\le y_k,
\qquad \forall k\in K,\ \forall p\in P
$$

若车辆 $k$ 被启用，则至少执行一趟任务：

$$
y_k\le \sum_{p\in P} z_{kp},
\qquad \forall k\in K
$$

---

## 7.5 趟次连续性约束

若车辆 $k$ 执行第 $p+1$ 趟，则必须已执行第 $p$ 趟：

$$
z_{k,p+1}\le z_{kp},
\qquad \forall k\in K,\ \forall p=1,2,\dots,P_{\max}-1
$$

---

## 7.6 车型数量约束

各车型实际启用车辆数不得超过可用数量：

$$
\sum_{k\in K_m} y_k\le n_m,
\qquad \forall m\in H
$$

---

## 7.7 每趟出发与回仓约束

每一趟任务若被启用，则必须从配送中心出发一次、返回一次：

$$
\sum_{j\in C}x_{0jkp}=z_{kp},
\qquad \forall k\in K,\ \forall p\in P
$$

$$
\sum_{i\in C}x_{i0kp}=z_{kp},
\qquad \forall k\in K,\ \forall p\in P
$$

---

## 7.8 客户访问与路径联动约束

若车辆 $k$ 的第 $p$ 趟服务客户 $i$，则该趟对客户 $i$ 必须进一次、出一次：

$$
\sum_{\substack{j\in N\\ j\neq i}}x_{ijkp}=\delta_{ikp},
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

$$
\sum_{\substack{j\in N\\ j\neq i}}x_{jikp}=\delta_{ikp},
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

因此，每辆车在每一趟中对同一客户至多访问一次。

---

## 7.9 弧上重量容量约束

任意车辆在任意趟次、任意弧上的重量载荷不得超过车辆最大载重：

$$
0\le f_{ijkp}\le Q_k x_{ijkp},
\qquad \forall (i,j)\in A,\ \forall k\in K,\ \forall p\in P
$$

---

## 7.10 弧上体积容量约束

任意车辆在任意趟次、任意弧上的体积载荷不得超过车辆最大容积：

$$
0\le g_{ijkp}\le U_k x_{ijkp},
\qquad \forall (i,j)\in A,\ \forall k\in K,\ \forall p\in P
$$

---

## 7.11 客户节点重量流守恒约束

车辆 $k$ 的第 $p$ 趟在客户 $i$ 处卸下的总重量，等于其在该趟被分配到客户 $i$ 的订单总重量：

$$
\sum_{\substack{h\in N\\ h\neq i}} f_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} f_{ijkp}
=
\sum_{r\in R_i} w_r\alpha_{rkp},
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

返回配送中心时，该趟剩余重量载荷为 0：

$$
f_{i0kp}=0,
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

---

## 7.12 客户节点体积流守恒约束

车辆 $k$ 的第 $p$ 趟在客户 $i$ 处卸下的总体积，等于其在该趟被分配到客户 $i$ 的订单总体积：

$$
\sum_{\substack{h\in N\\ h\neq i}} g_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} g_{ijkp}
=
\sum_{r\in R_i} v_r\alpha_{rkp},
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

返回配送中心时，该趟剩余体积载荷为 0：

$$
g_{i0kp}=0,
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

---

## 7.13 软时间窗约束

对每一次客户到访，等待时间与迟到时间定义为：

$$
W_{ikp}\ge a_i-A_{ikp}-B(1-\delta_{ikp}),
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

$$
L_{ikp}\ge A_{ikp}-b_i-B(1-\delta_{ikp}),
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

$$
W_{ikp}\ge 0,\qquad L_{ikp}\ge 0,
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

为便于数值求解，可进一步加上：

$$
A_{ikp}\le B\delta_{ikp},\qquad
W_{ikp}\le B\delta_{ikp},\qquad
L_{ikp}\le B\delta_{ikp}
$$

---

## 7.14 趟内时变旅行时间约束

若车辆 $k$ 的第 $p$ 趟从客户 $i$ 行驶至客户 $j$，则到达时刻满足：

$$
A_{jkp}
\ge
A_{ikp}+W_{ikp}+s_i+\tau_{ij}(A_{ikp}+W_{ikp}+s_i)-B(1-x_{ijkp}),
\qquad \forall i,j\in C,\ i\neq j,\ \forall k\in K,\ \forall p\in P
$$

若客户 $j$ 是车辆 $k$ 第 $p$ 趟从配送中心出发后的首个访问客户，则有：

$$
A_{jkp}
\ge
T_{kp}^{\mathrm{dep}}+\tau_{0j}(T_{kp}^{\mathrm{dep}})-B(1-x_{0jkp}),
\qquad \forall j\in C,\ \forall k\in K,\ \forall p\in P
$$

---

## 7.15 趟次返回时刻约束

若车辆 $k$ 的第 $p$ 趟最后从客户 $i$ 返回配送中心，则其回仓时刻满足：

$$
T_{kp}^{\mathrm{ret}}
\ge
A_{ikp}+W_{ikp}+s_i+\tau_{i0}(A_{ikp}+W_{ikp}+s_i)-B(1-x_{i0kp}),
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

---

## 7.16 多趟时间衔接约束

第一趟出发时刻不得早于计划期开始时刻：

$$
T_{k1}^{\mathrm{dep}}\ge t_0-B(1-z_{k1}),
\qquad \forall k\in K
$$

若车辆 $k$ 执行第 $p+1$ 趟，则其出发时刻不得早于第 $p$ 趟返回并完成重新装载之后：

$$
T_{k,p+1}^{\mathrm{dep}}
\ge
T_{kp}^{\mathrm{ret}}+\rho_k-B(1-z_{k,p+1}),
\qquad \forall k\in K,\ \forall p=1,2,\dots,P_{\max}-1
$$

同时：

$$
T_{kp}^{\mathrm{dep}}\le Bz_{kp},\qquad
T_{kp}^{\mathrm{ret}}\le Bz_{kp},
\qquad \forall k\in K,\ \forall p\in P
$$

---

## 7.17 变量取值约束

$$
x_{ijkp}\in\{0,1\},
\qquad \forall (i,j)\in A,\ \forall k\in K,\ \forall p\in P
$$

$$
\alpha_{rkp}\in\{0,1\},
\qquad \forall r\in R,\ \forall k\in K,\ \forall p\in P
$$

$$
\delta_{ikp}\in\{0,1\},
\qquad \forall i\in C,\ \forall k\in K,\ \forall p\in P
$$

$$
z_{kp}\in\{0,1\},
\qquad \forall k\in K,\ \forall p\in P
$$

$$
y_k\in\{0,1\},
\qquad \forall k\in K
$$

$$
A_{ikp},W_{ikp},L_{ikp},T_{kp}^{\mathrm{dep}},T_{kp}^{\mathrm{ret}},f_{ijkp},g_{ijkp}\ge 0
$$

---

## 8. 完整优化模型

综上，问题一的多趟优化模型可写为：

$$
\min Z=
\sum_{k\in K}F_k y_k
+
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^F\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^E\phi_{ijkp}^{E}
+
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^C\eta\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^C\gamma\phi_{ijkp}^{E}
+
c_w\sum_{i\in C}\sum_{k\in K}\sum_{p\in P}W_{ikp}
+
c_l\sum_{i\in C}\sum_{k\in K}\sum_{p\in P}L_{ikp}
$$

满足约束：

$$
\sum_{k\in K}\sum_{p\in P}\alpha_{rkp}=1,
\qquad \forall r\in R
$$

$$
\alpha_{rkp}\le \delta_{i(r)kp},
\qquad \forall r\in R,\forall k\in K,\forall p\in P
$$

$$
\delta_{ikp}\le \sum_{r\in R_i}\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
\sum_{k\in K}\sum_{p\in P}\delta_{ikp}\ge 1,
\qquad \forall i\in C
$$

$$
z_{kp}\le y_k,
\qquad \forall k\in K,\forall p\in P
$$

$$
y_k\le \sum_{p\in P}z_{kp},
\qquad \forall k\in K
$$

$$
z_{k,p+1}\le z_{kp},
\qquad \forall k\in K,\forall p=1,\dots,P_{\max}-1
$$

$$
\sum_{k\in K_m} y_k\le n_m,
\qquad \forall m\in H
$$

$$
\sum_{j\in C}x_{0jkp}=z_{kp},
\qquad \forall k\in K,\forall p\in P
$$

$$
\sum_{i\in C}x_{i0kp}=z_{kp},
\qquad \forall k\in K,\forall p\in P
$$

$$
\sum_{\substack{j\in N\\ j\neq i}}x_{ijkp}=\delta_{ikp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
\sum_{\substack{j\in N\\ j\neq i}}x_{jikp}=\delta_{ikp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
0\le f_{ijkp}\le Q_k x_{ijkp},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

$$
0\le g_{ijkp}\le U_k x_{ijkp},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

$$
\sum_{\substack{h\in N\\ h\neq i}} f_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} f_{ijkp}
=
\sum_{r\in R_i} w_r\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
\sum_{\substack{h\in N\\ h\neq i}} g_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} g_{ijkp}
=
\sum_{r\in R_i} v_r\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
f_{i0kp}=0,\qquad g_{i0kp}=0,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
W_{ikp}\ge a_i-A_{ikp}-B(1-\delta_{ikp}),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
L_{ikp}\ge A_{ikp}-b_i-B(1-\delta_{ikp}),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
A_{jkp}
\ge
A_{ikp}+W_{ikp}+s_i+\tau_{ij}(A_{ikp}+W_{ikp}+s_i)-B(1-x_{ijkp}),
\qquad \forall i,j\in C,\ i\neq j,\forall k\in K,\forall p\in P
$$

$$
A_{jkp}
\ge
T_{kp}^{\mathrm{dep}}+\tau_{0j}(T_{kp}^{\mathrm{dep}})-B(1-x_{0jkp}),
\qquad \forall j\in C,\forall k\in K,\forall p\in P
$$

$$
T_{kp}^{\mathrm{ret}}
\ge
A_{ikp}+W_{ikp}+s_i+\tau_{i0}(A_{ikp}+W_{ikp}+s_i)-B(1-x_{i0kp}),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
T_{k1}^{\mathrm{dep}}\ge t_0-B(1-z_{k1}),
\qquad \forall k\in K
$$

$$
T_{k,p+1}^{\mathrm{dep}}
\ge
T_{kp}^{\mathrm{ret}}+\rho_k-B(1-z_{k,p+1}),
\qquad \forall k\in K,\forall p=1,\dots,P_{\max}-1
$$

$$
x_{ijkp},\alpha_{rkp},\delta_{ikp},z_{kp},y_k\in\{0,1\}
$$

$$
A_{ikp},W_{ikp},L_{ikp},T_{kp}^{\mathrm{dep}},T_{kp}^{\mathrm{ret}},f_{ijkp},g_{ijkp}\ge 0
$$

---

## 9. 模型说明

该模型相较于单趟客户级 VRPTW 的主要改进体现在以下几个方面：

1. **订单不可拆分**：通过订单—车辆—趟次分配变量 $\alpha_{rkp}$ 保证每个订单完整地由一辆车的一趟任务承运；
2. **客户可拆可不拆**：通过客户—车辆—趟次服务变量 $\delta_{ikp}$ 允许客户由一个或多个车辆/趟次共同服务；
3. **单车允许多趟**：通过趟次启用变量 $z_{kp}$、趟次连续性约束和多趟时间衔接约束，允许同一车辆回仓后重新装载再出发；
4. **双容量约束**：同时使用重量流变量 $f_{ijkp}$ 和体积流变量 $g_{ijkp}$ 控制载重与容积限制；
5. **时变旅行时间**：通过 $\tau_{ij}(t)$ 表征车辆出发时刻对旅行时间的影响；
6. **绿色成本机制**：在传统路径优化目标中纳入能耗成本和碳排放成本；
7. **软时间窗机制**：允许早到或晚到，但通过等待成本和惩罚成本计入总目标函数。

因此，问题一最终被表述为一个：

$$
\text{多趟、异构、订单不可拆分、客户可分次服务的混合整数非线性规划模型（MINLP）}
$$

---

## 10. 可直接用于论文的总结性表述

针对问题一，本文建立了一个“订单不可拆分、客户可分次服务、单车允许多趟”的异构绿色车辆路径优化模型。模型以订单分配、客户服务、车辆路径、趟次安排和弧载荷为决策对象，在满足订单唯一分配、客户可被单车或多车服务、车辆多趟出入库、车型数量、重量与体积双容量、软时间窗及时变旅行时间等约束条件下，以固定启动车辆成本、能耗成本、碳排放成本、等待成本与迟到惩罚成本之和最小为优化目标，从而获得静态环境下的最优配送调度方案。