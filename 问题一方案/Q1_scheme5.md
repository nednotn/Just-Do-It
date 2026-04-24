# 问题一：静态环境下城市绿色物流配送调度模型（基于scheme4的最终版）

## 1. 问题描述

在无政策限制条件下，需要对某物流企业的城市配送任务进行优化调度。配送系统具有以下特征：

- 配送需求以订单为基本单位，同一客户点可能对应多个订单；
- 车辆为异构混合车队，不同车型具有不同的载重、容积和能源属性；
- 单个订单不可拆分，但同一客户的多个订单可由一辆车一次完成，也可由多辆车或同一车辆的不同趟次共同完成；
- 同一辆车在一个配送周期内允许多次往返配送中心，即完成一趟任务后返回中心重新装载并再次出发；
- 配送过程中同时受到重量容量、体积容量、软时间窗、时变速度、能耗成本与碳排放成本的影响。

因此，问题一建立为一个**订单不可拆分、客户可分次服务、单车允许多趟、双容量约束、软时间窗、时变速度的绿色车辆路径优化模型**。

---

## 2. 建模思路

问题一的决策过程由三个相互耦合的层面组成：

### 2.1 订单分配决策

以订单为最小配送单元，确定每个订单由哪一辆车的哪一趟任务承运，从而严格保证订单不可拆分。

### 2.2 路径与趟次调度决策

对每辆车的各趟任务分别规划访问路径、出发时刻、回仓时刻，并通过趟次间的时间衔接约束刻画同一车辆的重复利用过程。

### 2.3 载荷与时间耦合决策

通过重量流与体积流描述车辆在路径上的载荷变化，同时利用到达时刻变量刻画软时间窗成本，并将出发时刻嵌入时变旅行时间函数与能耗函数中，实现运输过程、时间过程与成本过程的一体化建模。

在此基础上，以固定启动车辆成本、能耗成本、碳排放成本、等待成本和迟到惩罚成本之和最小为目标，建立问题一的优化模型。

---

## 3. 模型假设

1. 原始数据以订单为基本单位，每个订单仅对应一个客户点，且单个订单不可拆分。
2. 路径中的服务节点以客户点表示，同一客户点可对应多个订单。
3. 同一客户的全部订单可由一辆车一次完成，也可由多辆车或同一车辆的不同趟次共同完成，具体由模型根据容量约束、时间约束与总成本自动决定。
4. 所有车辆均从配送中心出发，每趟任务结束后返回配送中心。
5. 同一车辆在同一计划日内允许执行多趟任务，且每次回仓后需消耗固定重新装载准备时间。
6. 每辆车在同一趟任务中对同一客户至多访问一次。
7. 每次车辆到访客户点均发生一次服务作业，服务时间固定为 20 分钟。
8. 软时间窗对每次到访均生效，提前到达产生等待成本，延迟到达产生惩罚成本。
9. 车辆速度受交通时段影响，在静态优化中采用各时段速度分布均值构造时变旅行时间函数。
10. 规划周期内每辆车的最大趟次数取为：
   $$
   P_{\max}=10
   $$

---

## 4. 符号说明

## 4.1 集合与索引

- $C=\{1,2,\dots,n\}$：客户集合；
- $N=\{0\}\cup C$：节点集合，其中 $0$ 表示配送中心；
- $R$：订单集合；
- $R_i\subseteq R$：客户 $i$ 对应的订单集合；
- $K$：车辆集合；
- $H$：车型集合；
- $K_h\subseteq K$：车型 $h$ 的车辆集合；
- $K^F\subseteq K$：燃油车集合；
- $K^E\subseteq K$：新能源车集合；
- $P=\{1,2,\dots,10\}$：单车可执行的趟次集合；
- $A=\{(i,j)\mid i,j\in N,\ i\neq j\}$：可行弧集合。

其中：

- $i,j$：节点索引；
- $r$：订单索引；
- $k$：车辆索引；
- $h$：车型索引；
- $p$：趟次索引。

---

## 4.2 参数定义

### （1）订单参数

- $w_r$：订单 $r$ 的重量（kg）；
- $v_r$：订单 $r$ 的体积（m$^3$）；
- $i(r)$：订单 $r$ 所属客户编号。

### （2）客户参数

- $[a_i,b_i]$：客户 $i$ 的软时间窗；
- $s_i$：客户 $i$ 的服务时间，题中取 20 分钟，即
  $$
  s_i=\frac{1}{3}\ \text{h}
  $$

客户 $i$ 的总需求统计量为：

$$
q_i=\sum_{r\in R_i} w_r
$$

$$
u_i=\sum_{r\in R_i} v_r
$$

其中 $q_i,u_i$ 仅表示客户需求统计量，不表示客户需求可以连续拆分。

### （3）车辆参数

- $Q_k$：车辆 $k$ 的最大载重（kg）；
- $U_k$：车辆 $k$ 的最大容积（m$^3$）；
- $F_k$：车辆 $k$ 的固定启用成本（元）；
- $n_h$：车型 $h$ 的可用车辆数；
- $\rho_k$：车辆 $k$ 每次返回配送中心后的重新装载准备时间（h）。

### （4）路网与时间参数

- $d_{ij}$：节点 $i$ 到节点 $j$ 的道路距离（km）；
- $\bar v(t)$：时刻 $t$ 对应的平均车速（km/h）；
- $\tau_{ij}(t)$：车辆在时刻 $t$ 从节点 $i$ 出发到达节点 $j$ 的旅行时间（h）；
- $t_0$：规划期起始时刻；
- $B$：足够大的正数。

### （5）成本参数

- $c_w=20$：单位等待成本（元/h）；
- $c_l=50$：单位迟到惩罚成本（元/h）；
- $p^F=7.61$：燃油价格（元/L）；
- $p^E=1.64$：电价（元/(kW$\cdot$h)）；
- $p^C=0.65$：单位碳排放成本（元/kg）。

### （6）能耗与碳排放参数

燃油车百公里油耗函数为：

$$
FPK(v)=0.0025v^2-0.2554v+31.75
$$

新能源车百公里电耗函数为：

$$
EPK(v)=0.0014v^2-0.12v+36.19
$$

载荷附加系数取：

- 燃油车：$0.4$；
- 新能源车：$0.35$。

碳排放系数取：

- 燃油车：$\eta=2.547$ kg/L；
- 新能源车：$\gamma=0.501$ kg/(kW$\cdot$h)。

---

## 5. 时变速度函数

依据题意，将各时段速度分布的均值作为静态优化中的平均速度，得到：

$$
\bar v(t)=
\begin{cases}
9.8, & t\in [8{:}00,9{:}00)\cup[11{:}30,13{:}00) \\
35.4, & t\in [10{:}00,11{:}30)\cup[15{:}00,17{:}00) \\
55.3, & t\in [9{:}00,10{:}00)\cup[13{:}00,15{:}00)
\end{cases}
$$

相应地，定义时变旅行时间函数：

$$
\tau_{ij}(t)=\text{车辆在时刻 }t\text{ 从节点 }i\text{ 出发到达节点 }j\text{ 所需旅行时间}
$$

若行程跨越多个交通时段，则采用分段累计法计算总旅行时间。

---

## 6. 决策变量

### 6.1 订单分配变量

$$
\alpha_{rkp}=
\begin{cases}
1, & \text{若订单 }r\text{ 由车辆 }k\text{ 的第 }p\text{ 趟承运} \\
0, & \text{否则}
\end{cases}
$$

### 6.2 路径变量

$$
x_{ijkp}=
\begin{cases}
1, & \text{若车辆 }k\text{ 在第 }p\text{ 趟从节点 }i\text{ 行驶到节点 }j \\
0, & \text{否则}
\end{cases}
$$

### 6.3 趟次启用变量

$$
z_{kp}=
\begin{cases}
1, & \text{若车辆 }k\text{ 执行第 }p\text{ 趟任务} \\
0, & \text{否则}
\end{cases}
$$

### 6.4 弧载荷变量

- $f_{ijkp}$：车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上承载的重量载荷（kg）；
- $g_{ijkp}$：车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上承载的体积载荷（m$^3$）。

### 6.5 时间变量

- $A_{ikp}$：车辆 $k$ 在第 $p$ 趟到达客户 $i$ 的时刻；
- $W_{ikp}$：车辆 $k$ 在第 $p$ 趟于客户 $i$ 的等待时间；
- $L_{ikp}$：车辆 $k$ 在第 $p$ 趟于客户 $i$ 的迟到时间；
- $T_{kp}^{\mathrm{dep}}$：车辆 $k$ 第 $p$ 趟从配送中心出发时刻；
- $T_{kp}^{\mathrm{ret}}$：车辆 $k$ 第 $p$ 趟返回配送中心时刻。

---

## 7. 目标函数

以总配送成本最小为目标：

$$
\min Z=C_{\text{fix}}+C_{\text{ene}}+C_{\text{car}}+C_{\text{wait}}+C_{\text{late}}
$$

### 7.1 固定启动车辆成本

车辆是否被启用等价于其第一趟是否被激活，因此：

$$
C_{\text{fix}}=\sum_{k\in K} F_k z_{k1}
$$

### 7.2 弧上出发时刻

定义弧 $(i,j)$ 的实际出发时刻为：

$$
\theta_{ijkp}=
\begin{cases}
T_{kp}^{\mathrm{dep}}, & i=0 \\
A_{ikp}+W_{ikp}+s_i, & i\in C
\end{cases}
$$

并定义对应时段速度为：

$$
v_{ijkp}=\bar v(\theta_{ijkp})
$$

### 7.3 能耗成本

定义车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上的重量载荷率为：

$$
\lambda_{ijkp}=\frac{f_{ijkp}}{Q_k}
$$

若 $k\in K^F$，则油耗量为：

$$
\phi_{ijkp}^{F}
=
\frac{d_{ij}}{100}\cdot FPK(v_{ijkp})\cdot (1+0.4\lambda_{ijkp})
$$

若 $k\in K^E$，则电耗量为：

$$
\phi_{ijkp}^{E}
=
\frac{d_{ij}}{100}\cdot EPK(v_{ijkp})\cdot (1+0.35\lambda_{ijkp})
$$

于是总能耗成本为：

$$
C_{\text{ene}}
=
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^F\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^E\phi_{ijkp}^{E}
$$

### 7.4 碳排放成本

$$
C_{\text{car}}
=
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^C\eta\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^C\gamma\phi_{ijkp}^{E}
$$

### 7.5 等待成本

$$
C_{\text{wait}}=c_w\sum_{i\in C}\sum_{k\in K}\sum_{p\in P} W_{ikp}
$$

### 7.6 迟到惩罚成本

$$
C_{\text{late}}=c_l\sum_{i\in C}\sum_{k\in K}\sum_{p\in P} L_{ikp}
$$

---

## 8. 约束条件

## 8.1 订单唯一分配约束

每个订单必须且只能由一辆车的一趟任务承运：

$$
\sum_{k\in K}\sum_{p\in P}\alpha_{rkp}=1,
\qquad \forall r\in R
$$

---

## 8.2 订单分配与路径访问联动约束

若订单 $r$ 由车辆 $k$ 的第 $p$ 趟承运，则该趟必须访问订单所属客户：

$$
\alpha_{rkp}\le \sum_{\substack{j\in N\\ j\neq i(r)}} x_{i(r)jkp},
\qquad \forall r\in R,\forall k\in K,\forall p\in P
$$

若车辆 $k$ 的第 $p$ 趟访问客户 $i$，则该趟至少承运客户 $i$ 的一个订单：

$$
\sum_{\substack{j\in N\\ j\neq i}} x_{jikp}
\le
\sum_{r\in R_i}\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

---

## 8.3 单趟客户流平衡与至多一次访问约束

对任意客户 $i$、车辆 $k$ 和趟次 $p$，有：

$$
\sum_{\substack{j\in N\\ j\neq i}} x_{ijkp}
=
\sum_{\substack{j\in N\\ j\neq i}} x_{jikp}
\le 1,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

该约束表示：

- 若该趟访问客户 $i$，则必然进一次、出一次；
- 若不访问，则入边与出边均为 0；
- 同一辆车在同一趟中对同一客户至多访问一次。

---

## 8.4 每趟出发与回仓约束

若车辆 $k$ 的第 $p$ 趟被启用，则该趟必须从配送中心出发一次并返回一次：

$$
\sum_{j\in C} x_{0jkp}=z_{kp},
\qquad \forall k\in K,\forall p\in P
$$

$$
\sum_{i\in C} x_{i0kp}=z_{kp},
\qquad \forall k\in K,\forall p\in P
$$

---

## 8.5 趟次连续性约束

若车辆 $k$ 执行第 $p+1$ 趟，则必须已执行第 $p$ 趟：

$$
z_{k,p+1}\le z_{kp},
\qquad \forall k\in K,\forall p=1,2,\dots,9
$$

---

## 8.6 车型数量约束

车辆是否启用由第一趟是否激活表示，因此：

$$
\sum_{k\in K_h} z_{k1}\le n_h,
\qquad \forall h\in H
$$

---

## 8.7 弧上重量容量约束

$$
0\le f_{ijkp}\le Q_k x_{ijkp},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

---

## 8.8 弧上体积容量约束

$$
0\le g_{ijkp}\le U_k x_{ijkp},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

---

## 8.9 客户节点重量流守恒约束

车辆 $k$ 的第 $p$ 趟在客户 $i$ 处卸下的总重量，等于该趟被分配到客户 $i$ 的订单总重量：

$$
\sum_{\substack{h\in N\\ h\neq i}} f_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} f_{ijkp}
=
\sum_{r\in R_i} w_r\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

回仓时剩余重量载荷为 0：

$$
f_{i0kp}=0,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

---

## 8.10 客户节点体积流守恒约束

车辆 $k$ 的第 $p$ 趟在客户 $i$ 处卸下的总体积，等于该趟被分配到客户 $i$ 的订单总体积：

$$
\sum_{\substack{h\in N\\ h\neq i}} g_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} g_{ijkp}
=
\sum_{r\in R_i} v_r\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

回仓时剩余体积载荷为 0：

$$
g_{i0kp}=0,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

---

## 8.11 软时间窗约束

由路径变量直接激活时间窗约束：

$$
W_{ikp}
\ge
a_i-A_{ikp}
-
B\left(1-\sum_{\substack{j\in N\\ j\neq i}}x_{jikp}\right),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
L_{ikp}
\ge
A_{ikp}-b_i
-
B\left(1-\sum_{\substack{j\in N\\ j\neq i}}x_{jikp}\right),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
W_{ikp}\ge 0,\qquad L_{ikp}\ge 0,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

---

## 8.12 趟内时变旅行时间约束

若车辆 $k$ 的第 $p$ 趟从客户 $i$ 行驶到客户 $j$，则有：

$$
A_{jkp}
\ge
A_{ikp}+W_{ikp}+s_i+\tau_{ij}(A_{ikp}+W_{ikp}+s_i)
-B(1-x_{ijkp}),
\qquad \forall i,j\in C,\ i\neq j,\forall k\in K,\forall p\in P
$$

若客户 $j$ 是车辆 $k$ 第 $p$ 趟从配送中心出发后的首个访问客户，则有：

$$
A_{jkp}
\ge
T_{kp}^{\mathrm{dep}}+\tau_{0j}(T_{kp}^{\mathrm{dep}})
-B(1-x_{0jkp}),
\qquad \forall j\in C,\forall k\in K,\forall p\in P
$$

---

## 8.13 趟次返回时刻约束

若车辆 $k$ 的第 $p$ 趟最后从客户 $i$ 返回配送中心，则有：

$$
T_{kp}^{\mathrm{ret}}
\ge
A_{ikp}+W_{ikp}+s_i+\tau_{i0}(A_{ikp}+W_{ikp}+s_i)
-B(1-x_{i0kp}),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

---

## 8.14 多趟时间衔接约束

第一趟出发时刻不得早于规划期开始时刻：

$$
T_{k1}^{\mathrm{dep}}\ge t_0-B(1-z_{k1}),
\qquad \forall k\in K
$$

若车辆 $k$ 执行第 $p+1$ 趟，则该趟出发时刻不得早于第 $p$ 趟返回并完成重新装载之后：

$$
T_{k,p+1}^{\mathrm{dep}}
\ge
T_{kp}^{\mathrm{ret}}+\rho_k-B(1-z_{k,p+1}),
\qquad \forall k\in K,\forall p=1,2,\dots,9
$$

---

## 8.15 变量取值约束

$$
x_{ijkp}\in\{0,1\},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

$$
\alpha_{rkp}\in\{0,1\},
\qquad \forall r\in R,\forall k\in K,\forall p\in P
$$

$$
z_{kp}\in\{0,1\},
\qquad \forall k\in K,\forall p\in P
$$

$$
A_{ikp},W_{ikp},L_{ikp},T_{kp}^{\mathrm{dep}},T_{kp}^{\mathrm{ret}},f_{ijkp},g_{ijkp}\ge 0
$$

---

## 9. 完整优化模型

### 9.1 目标函数

$$
\min Z=C_{\text{fix}}+C_{\text{ene}}+C_{\text{car}}+C_{\text{wait}}+C_{\text{late}}
$$

其中：

#### （1）固定启动车辆成本

$$
C_{\text{fix}}=\sum_{k\in K}F_k z_{k1}
$$

#### （2）能耗成本

对燃油车：

$$
\phi_{ijkp}^{F}
=
\frac{d_{ij}}{100}\cdot FPK(v_{ijkp})\cdot \left(1+0.4\frac{f_{ijkp}}{Q_k}\right)
$$

对新能源车：

$$
\phi_{ijkp}^{E}
=
\frac{d_{ij}}{100}\cdot EPK(v_{ijkp})\cdot \left(1+0.35\frac{f_{ijkp}}{Q_k}\right)
$$

于是总能耗成本为：

$$
C_{\text{ene}}
=
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^F\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^E\phi_{ijkp}^{E}
$$

#### （3）碳排放成本

$$
C_{\text{car}}
=
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^C\eta\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^C\gamma\phi_{ijkp}^{E}
$$

#### （4）等待成本

$$
C_{\text{wait}}
=
c_w\sum_{i\in C}\sum_{k\in K}\sum_{p\in P} W_{ikp}
$$

#### （5）迟到惩罚成本

$$
C_{\text{late}}
=
c_l\sum_{i\in C}\sum_{k\in K}\sum_{p\in P} L_{ikp}
$$

---

### 9.2 约束条件

#### （1）订单唯一分配约束

$$
\sum_{k\in K}\sum_{p\in P}\alpha_{rkp}=1,
\qquad \forall r\in R
$$

#### （2）订单分配与路径访问联动约束

$$
\alpha_{rkp}\le \sum_{\substack{j\in N\\ j\neq i(r)}} x_{i(r)jkp},
\qquad \forall r\in R,\forall k\in K,\forall p\in P
$$

$$
\sum_{\substack{j\in N\\ j\neq i}} x_{jikp}
\le
\sum_{r\in R_i}\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

#### （3）单趟客户流平衡与至多一次访问约束

$$
\sum_{\substack{j\in N\\ j\neq i}} x_{ijkp}
=
\sum_{\substack{j\in N\\ j\neq i}} x_{jikp}
\le 1,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

#### （4）每趟出发与回仓约束

$$
\sum_{j\in C} x_{0jkp}=z_{kp},
\qquad \forall k\in K,\forall p\in P
$$

$$
\sum_{i\in C} x_{i0kp}=z_{kp},
\qquad \forall k\in K,\forall p\in P
$$

#### （5）趟次连续性约束

$$
z_{k,p+1}\le z_{kp},
\qquad \forall k\in K,\forall p=1,2,\dots,9
$$

#### （6）车型数量约束

$$
\sum_{k\in K_h} z_{k1}\le n_h,
\qquad \forall h\in H
$$

#### （7）弧上重量容量约束

$$
0\le f_{ijkp}\le Q_k x_{ijkp},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

#### （8）弧上体积容量约束

$$
0\le g_{ijkp}\le U_k x_{ijkp},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

#### （9）客户节点重量流守恒约束

$$
\sum_{\substack{h\in N\\ h\neq i}} f_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} f_{ijkp}
=
\sum_{r\in R_i} w_r\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
f_{i0kp}=0,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

#### （10）客户节点体积流守恒约束

$$
\sum_{\substack{h\in N\\ h\neq i}} g_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} g_{ijkp}
=
\sum_{r\in R_i} v_r\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
g_{i0kp}=0,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

#### （11）软时间窗约束

$$
W_{ikp}
\ge
a_i-A_{ikp}
-
B\left(1-\sum_{\substack{j\in N\\ j\neq i}}x_{jikp}\right),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
L_{ikp}
\ge
A_{ikp}-b_i
-
B\left(1-\sum_{\substack{j\in N\\ j\neq i}}x_{jikp}\right),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

$$
W_{ikp}\ge 0,\qquad L_{ikp}\ge 0,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

#### （12）趟内时变旅行时间约束

$$
A_{jkp}
\ge
A_{ikp}+W_{ikp}+s_i+\tau_{ij}(A_{ikp}+W_{ikp}+s_i)
-B(1-x_{ijkp}),
\qquad \forall i,j\in C,\ i\neq j,\forall k\in K,\forall p\in P
$$

$$
A_{jkp}
\ge
T_{kp}^{\mathrm{dep}}+\tau_{0j}(T_{kp}^{\mathrm{dep}})
-B(1-x_{0jkp}),
\qquad \forall j\in C,\forall k\in K,\forall p\in P
$$

#### （13）趟次返回时刻约束

$$
T_{kp}^{\mathrm{ret}}
\ge
A_{ikp}+W_{ikp}+s_i+\tau_{i0}(A_{ikp}+W_{ikp}+s_i)
-B(1-x_{i0kp}),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

#### （14）多趟时间衔接约束

$$
T_{k1}^{\mathrm{dep}}\ge t_0-B(1-z_{k1}),
\qquad \forall k\in K
$$

$$
T_{k,p+1}^{\mathrm{dep}}
\ge
T_{kp}^{\mathrm{ret}}+\rho_k-B(1-z_{k,p+1}),
\qquad \forall k\in K,\forall p=1,2,\dots,9
$$

#### （15）变量取值约束

$$
x_{ijkp}\in\{0,1\},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

$$
\alpha_{rkp}\in\{0,1\},
\qquad \forall r\in R,\forall k\in K,\forall p\in P
$$

$$
z_{kp}\in\{0,1\},
\qquad \forall k\in K,\forall p\in P
$$

$$
A_{ikp},W_{ikp},L_{ikp},T_{kp}^{\mathrm{dep}},T_{kp}^{\mathrm{ret}},f_{ijkp},g_{ijkp}\ge 0
$$

---

### 9.3 模型的紧凑表示

因此，问题一的完整优化模型可简记为：

$$
\begin{aligned}
\min \quad & Z \\
\text{s.t.}\quad
& \sum_{k\in K}\sum_{p\in P}\alpha_{rkp}=1, && \forall r\in R \\
& \alpha_{rkp}\le \sum_{j\neq i(r)}x_{i(r)jkp}, && \forall r,k,p \\
& \sum_{j\neq i}x_{jikp}\le \sum_{r\in R_i}\alpha_{rkp}, && \forall i,k,p \\
& \sum_{j\neq i}x_{ijkp}=\sum_{j\neq i}x_{jikp}\le 1, && \forall i,k,p \\
& \sum_{j\in C}x_{0jkp}=z_{kp}, && \forall k,p \\
& \sum_{i\in C}x_{i0kp}=z_{kp}, && \forall k,p \\
& z_{k,p+1}\le z_{kp}, && \forall k,\ p=1,\dots,9 \\
& \sum_{k\in K_h}z_{k1}\le n_h, && \forall h\in H \\
& 0\le f_{ijkp}\le Q_kx_{ijkp}, && \forall (i,j),k,p \\
& 0\le g_{ijkp}\le U_kx_{ijkp}, && \forall (i,j),k,p \\
& \sum_{h\neq i}f_{hikp}-\sum_{j\neq i}f_{ijkp}=\sum_{r\in R_i}w_r\alpha_{rkp}, && \forall i,k,p \\
& \sum_{h\neq i}g_{hikp}-\sum_{j\neq i}g_{ijkp}=\sum_{r\in R_i}v_r\alpha_{rkp}, && \forall i,k,p \\
& f_{i0kp}=0,\ g_{i0kp}=0, && \forall i,k,p \\
& W_{ikp}\ge a_i-A_{ikp}-B\Bigl(1-\sum_{j\neq i}x_{jikp}\Bigr), && \forall i,k,p \\
& L_{ikp}\ge A_{ikp}-b_i-B\Bigl(1-\sum_{j\neq i}x_{jikp}\Bigr), && \forall i,k,p \\
& A_{jkp}\ge A_{ikp}+W_{ikp}+s_i+\tau_{ij}(A_{ikp}+W_{ikp}+s_i)-B(1-x_{ijkp}), && \forall i\neq j,k,p \\
& A_{jkp}\ge T_{kp}^{\mathrm{dep}}+\tau_{0j}(T_{kp}^{\mathrm{dep}})-B(1-x_{0jkp}), && \forall j,k,p \\
& T_{kp}^{\mathrm{ret}}\ge A_{ikp}+W_{ikp}+s_i+\tau_{i0}(A_{ikp}+W_{ikp}+s_i)-B(1-x_{i0kp}), && \forall i,k,p \\
& T_{k1}^{\mathrm{dep}}\ge t_0-B(1-z_{k1}), && \forall k \\
& T_{k,p+1}^{\mathrm{dep}}\ge T_{kp}^{\mathrm{ret}}+\rho_k-B(1-z_{k,p+1}), && \forall k,\ p=1,\dots,9 \\
& x_{ijkp},\alpha_{rkp},z_{kp}\in\{0,1\}, \\
& A_{ikp},W_{ikp},L_{ikp},T_{kp}^{\mathrm{dep}},T_{kp}^{\mathrm{ret}},f_{ijkp},g_{ijkp}\ge 0.
\end{aligned}
$$

---

### 9.4 模型说明

上述模型完整刻画了以下业务特征：

- 订单层面的唯一分配与不可拆分；
- 客户层面的单次或多次服务；
- 车辆层面的多趟重复利用；
- 运输过程中的重量与体积双资源约束；
- 服务过程中的软时间窗约束；
- 路径过程中的时变旅行时间；
- 成本结构中的固定成本、能耗成本、碳排放成本、等待成本与迟到惩罚成本。

因此，该模型能够作为问题一的完整数学优化框架，用于后续的算法设计与数值求解。
问题一最终可归结为一个**混合整数非线性规划模型（MINLP）**。若后续对旅行时间函数和能耗函数进行分段线性化，则可进一步转化为**混合整数线性规划近似模型（MILP）**。


---

## 10. 模型特点

该模型具有以下特点：

1. 以订单为最小分配单元，严格保证订单不可拆分；
2. 以客户点为路径节点，允许客户由单车或多车、多趟完成配送；
3. 通过趟次索引刻画车辆重复利用过程，符合城市配送中“回仓补货再出发”的实际运行方式；
4. 通过重量流和体积流同时约束双容量，可准确描述配送过程中的载荷变化；
5. 通过时变旅行时间函数和能耗函数刻画交通状态变化对运输成本的影响；
6. 采用紧凑型建模方式，直接利用路径变量表达客户访问状态，从而降低变量与约束数量。

因此，问题一最终可表述为一个**多趟、异构、订单不可拆分、客户可分次服务的紧凑型绿色车辆路径优化模型**。

---

## 11. 论文中的总结性表述

针对问题一，建立了一个以总配送成本最小为目标的多趟异构绿色车辆路径优化模型。模型以订单分配、车辆路径、趟次安排和弧载荷传播为核心决策对象，在满足订单唯一分配、客户访问与订单联动、车辆多趟出入库、车型数量限制、重量与体积双容量、软时间窗及时变旅行时间等约束条件下，对固定启动车辆成本、能耗成本、碳排放成本、等待成本与迟到惩罚成本进行综合优化，从而得到静态环境下的最优配送调度方案。