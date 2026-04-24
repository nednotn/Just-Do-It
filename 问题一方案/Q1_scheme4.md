# 问题一：静态环境下城市绿色物流配送调度模型（简化约束版）

## 1. 问题概述

在无政策限制条件下，需要对某物流企业的城市配送任务进行优化调度。配送系统具有如下特征：

- 配送需求由订单构成，同一客户点可能对应多个订单；
- 车辆为异构混合车队，存在不同载重与容积上限；
- 单个订单不可拆分，但同一客户的多个订单可由一辆车一次完成，也可由多辆车或同一车辆的不同趟次共同完成；
- 单辆车在一个计划期内允许执行多趟任务，即完成一趟后返回配送中心重新装载再出发；
- 配送过程中同时受软时间窗、时变交通速度、能耗成本和碳排放成本影响。

因此，问题一可建模为一个：

$$
\text{订单不可拆分、客户可分次服务、单车允许多趟、双容量约束、软时间窗、时变速度的绿色车辆路径优化模型}
$$

---

## 2. 建模思路

### 2.1 基本思想

将问题一拆解为两个相互耦合的决策层：

1. **订单分配层**  
   决定每个订单由哪一辆车的哪一趟任务承运，保证订单不可拆分。

2. **路径与趟次调度层**  
   决定每辆车每一趟的访问路径、出发时间、返回时间以及不同趟次之间的时间衔接。

在此基础上，通过重量流与体积流变量同时控制双容量约束，并通过到达时间变量刻画软时间窗与时变速度影响，最终以总成本最小为目标构造优化模型。

---

### 2.2 简化约束的核心思路

在保持建模思想不变的前提下，对约束系统进行以下简化：

1. **删除客户—车辆—趟次服务变量**  
   不再单独设置“某客户是否被某车某趟服务”的二元变量，而直接由路径变量判断客户是否被访问。

2. **删除车辆启用变量**  
   利用趟次连续性，将“车辆是否启用”等价表示为“该车第一趟是否被激活”。

3. **删除客户至少服务一次约束**  
   因为“订单唯一分配 + 订单与路径联动”已经能够逻辑上保证客户被服务。

因此，模型在保持原有业务语义的同时，显著减少了二元变量与联动约束数量。

---

## 3. 模型假设

1. 原始数据以订单为基本单位，每个订单仅对应一个客户点，且订单不可拆分。
2. 路径节点以客户点表示，同一客户点可以对应多个订单。
3. 同一客户是否由单车一次完成，或由多车/多趟分次完成，不预先指定，而由优化模型自动决定。
4. 所有车辆均从配送中心出发，每趟任务结束后返回配送中心；同一车辆在计划期内允许执行多趟任务。
5. 每辆车在同一趟任务中对同一客户至多访问一次。
6. 每次车辆到访客户均发生一次服务作业，服务时间固定为 20 分钟。
7. 软时间窗对每次客户到访均生效，提前到达产生等待成本，迟到到达产生惩罚成本。
8. 车辆速度受时段影响，静态优化中采用各时段速度分布均值构造时变旅行时间函数。
9. 车辆每次回到配送中心后需要固定的重新装载准备时间。
10. 规划期内每辆车的最大趟次数设为充分大的上界 $P_{\max}$。

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
- $P=\{1,2,\dots,P_{\max}\}$：单车可执行的趟次集合；
- $A=\{(i,j)\mid i,j\in N,\ i\neq j\}$：可行弧集合。

---

## 4.2 参数定义

### （1）订单参数

- $w_r$：订单 $r$ 的重量（kg）；
- $v_r$：订单 $r$ 的体积（m$^3$）；
- $i(r)$：订单 $r$ 所属客户编号。

### （2）客户参数

- $[a_i,b_i]$：客户 $i$ 的软时间窗；
- $s_i$：客户 $i$ 的服务时间，题中取 $20$ 分钟，即 $\frac{1}{3}$ 小时。

客户 $i$ 的总需求统计量为：

$$
q_i=\sum_{r\in R_i} w_r, \qquad
u_i=\sum_{r\in R_i} v_r
$$

其中 $q_i,u_i$ 仅用于统计分析，不表示客户需求可连续拆分。

### （3）车辆参数

- $Q_k$：车辆 $k$ 的最大载重（kg）；
- $U_k$：车辆 $k$ 的最大容积（m$^3$）；
- $F_k$：车辆 $k$ 的固定启用成本（元）；
- $n_h$：车型 $h$ 的可用车辆数；
- $\rho_k$：车辆 $k$ 每次回仓后的重新装载准备时间（h）。

### （4）路网与时间参数

- $d_{ij}$：节点 $i$ 到节点 $j$ 的道路距离（km）；
- $\bar v(t)$：时刻 $t$ 对应的平均车速（km/h）；
- $\tau_{ij}(t)$：车辆在时刻 $t$ 从节点 $i$ 出发到达节点 $j$ 的旅行时间（h）；
- $t_0$：规划期起始时刻；
- $B$：足够大的正数（Big-M 常数）。

### （5）成本参数

- $c_w$：单位等待成本（元/h）；
- $c_l$：单位迟到惩罚成本（元/h）；
- $p^F$：燃油价格（元/L）；
- $p^E$：电价（元/(kW$\cdot$h)）；
- $p^C$：单位碳排放成本（元/kg）。

### （6）能耗与排放参数

燃油车百公里油耗函数：

$$
FPK(v)=0.0025v^2-0.2554v+31.75
$$

新能源车百公里电耗函数：

$$
EPK(v)=0.0014v^2-0.12v+36.19
$$

载荷附加系数：

- 燃油车：$0.4$；
- 新能源车：$0.35$。

碳排放系数：

- 燃油车：$\eta$；
- 新能源车：$\gamma$。

---

## 5. 决策变量

### 5.1 订单分配变量

$$
\alpha_{rkp}=
\begin{cases}
1, & \text{若订单 }r\text{ 由车辆 }k\text{ 的第 }p\text{ 趟承运} \\
0, & \text{否则}
\end{cases}
\qquad \forall r\in R,\forall k\in K,\forall p\in P
$$

### 5.2 路径变量

$$
x_{ijkp}=
\begin{cases}
1, & \text{若车辆 }k\text{ 在第 }p\text{ 趟从节点 }i\text{ 行驶到节点 }j \\
0, & \text{否则}
\end{cases}
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

### 5.3 趟次启用变量

$$
z_{kp}=
\begin{cases}
1, & \text{若车辆 }k\text{ 执行第 }p\text{ 趟任务} \\
0, & \text{否则}
\end{cases}
\qquad \forall k\in K,\forall p\in P
$$

### 5.4 弧载荷变量

- $f_{ijkp}$：车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上承载的重量载荷（kg）；
- $g_{ijkp}$：车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上承载的体积载荷（m$^3$）。

### 5.5 时间变量

- $A_{ikp}$：车辆 $k$ 在第 $p$ 趟到达客户 $i$ 的时刻；
- $W_{ikp}$：车辆 $k$ 在第 $p$ 趟于客户 $i$ 的等待时间；
- $L_{ikp}$：车辆 $k$ 在第 $p$ 趟于客户 $i$ 的迟到时间；
- $T_{kp}^{\mathrm{dep}}$：车辆 $k$ 第 $p$ 趟从配送中心出发时刻；
- $T_{kp}^{\mathrm{ret}}$：车辆 $k$ 第 $p$ 趟返回配送中心时刻。

---

## 6. 目标函数

总成本由五部分构成：

1. 车辆固定启用成本；
2. 能耗成本；
3. 碳排放成本；
4. 等待成本；
5. 迟到惩罚成本。

因此目标函数为：

$$
\min Z=C_{\text{fix}}+C_{\text{ene}}+C_{\text{car}}+C_{\text{wait}}+C_{\text{late}}
$$

### 6.1 固定启用成本

由于采用趟次连续性约束，车辆是否启用可由第一趟是否被激活表示，因此：

$$
C_{\text{fix}}=\sum_{k\in K}F_k z_{k1}
$$

### 6.2 弧上能耗与碳排放成本

定义车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 上的重量载荷率为：

$$
\lambda_{ijkp}=\frac{f_{ijkp}}{Q_k}
$$

若 $k\in K^F$，则该弧油耗量为：

$$
\phi_{ijkp}^{F}
=
\frac{d_{ij}}{100}
\cdot
FPK(v_{ijkp})
\cdot
(1+0.4\lambda_{ijkp})
$$

若 $k\in K^E$，则该弧电耗量为：

$$
\phi_{ijkp}^{E}
=
\frac{d_{ij}}{100}
\cdot
EPK(v_{ijkp})
\cdot
(1+0.35\lambda_{ijkp})
$$

其中，$v_{ijkp}$ 表示车辆 $k$ 在第 $p$ 趟弧 $(i,j)$ 出发时对应的时段速度。

于是：

$$
C_{\text{ene}}
=
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^F\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^E\phi_{ijkp}^{E}
$$

$$
C_{\text{car}}
=
\sum_{k\in K^F}\sum_{p\in P}\sum_{(i,j)\in A} p^C\eta\phi_{ijkp}^{F}
+
\sum_{k\in K^E}\sum_{p\in P}\sum_{(i,j)\in A} p^C\gamma\phi_{ijkp}^{E}
$$

### 6.3 等待成本与迟到惩罚成本

$$
C_{\text{wait}}=c_w\sum_{i\in C}\sum_{k\in K}\sum_{p\in P}W_{ikp}
$$

$$
C_{\text{late}}=c_l\sum_{i\in C}\sum_{k\in K}\sum_{p\in P}L_{ikp}
$$

---

## 7. 简化后的约束条件

## 7.1 订单唯一分配约束

每个订单必须且只能由一辆车的一趟任务承运：

$$
\sum_{k\in K}\sum_{p\in P}\alpha_{rkp}=1,
\qquad \forall r\in R
$$

该约束直接保证订单不可拆分。

---

## 7.2 订单分配与路径访问联动约束

若订单 $r$ 由车辆 $k$ 的第 $p$ 趟承运，则该趟必须访问订单所属客户：

$$
\alpha_{rkp}\le \sum_{\substack{j\in N\\ j\neq i(r)}} x_{i(r)jkp},
\qquad \forall r\in R,\forall k\in K,\forall p\in P
$$

反之，若某趟访问了客户 $i$，则该趟至少承运客户 $i$ 的一个订单：

$$
\sum_{\substack{j\in N\\ j\neq i}} x_{jikp}
\le
\sum_{r\in R_i}\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

这两组约束共同替代了原先的客户服务指示变量。

---

## 7.3 单趟客户流平衡与至多一次访问约束

对任意客户 $i$、车辆 $k$ 和趟次 $p$，若该趟访问客户 $i$，则必须进一次、出一次；若不访问，则入边和出边均为 0：

$$
\sum_{\substack{j\in N\\ j\neq i}} x_{ijkp}
=
\sum_{\substack{j\in N\\ j\neq i}} x_{jikp}
\le 1,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

该约束保证：

- 同一辆车在同一趟中对同一客户至多访问一次；
- 同一趟可以服务多个客户，但对每个被访问客户只停靠一次。

---

## 7.4 每趟出发与回仓约束

若车辆 $k$ 的第 $p$ 趟被启用，则该趟必须从配送中心出发一次、返回一次：

$$
\sum_{j\in C} x_{0jkp}=z_{kp},
\qquad \forall k\in K,\forall p\in P
$$

$$
\sum_{i\in C} x_{i0kp}=z_{kp},
\qquad \forall k\in K,\forall p\in P
$$

---

## 7.5 趟次连续性约束

若车辆 $k$ 执行第 $p+1$ 趟，则必须已经执行第 $p$ 趟：

$$
z_{k,p+1}\le z_{kp},
\qquad \forall k\in K,\forall p=1,2,\dots,P_{\max}-1
$$

该约束既符合业务逻辑，也能减少模型对称性。

---

## 7.6 车型数量约束

由于车辆是否启用可由第一趟是否激活表示，因此车型数量约束写为：

$$
\sum_{k\in K_h} z_{k1}\le n_h,
\qquad \forall h\in H
$$

---

## 7.7 弧上重量容量约束

任意车辆在任意趟次、任意弧上的重量载荷不得超过最大载重：

$$
0\le f_{ijkp}\le Q_k x_{ijkp},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

---

## 7.8 弧上体积容量约束

任意车辆在任意趟次、任意弧上的体积载荷不得超过最大容积：

$$
0\le g_{ijkp}\le U_k x_{ijkp},
\qquad \forall (i,j)\in A,\forall k\in K,\forall p\in P
$$

---

## 7.9 客户节点重量流守恒约束

车辆 $k$ 的第 $p$ 趟在客户 $i$ 处卸下的总重量，等于该趟被分配到客户 $i$ 的订单总重量：

$$
\sum_{\substack{h\in N\\ h\neq i}} f_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} f_{ijkp}
=
\sum_{r\in R_i} w_r\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

且回仓时该趟剩余重量载荷为 0：

$$
f_{i0kp}=0,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

---

## 7.10 客户节点体积流守恒约束

车辆 $k$ 的第 $p$ 趟在客户 $i$ 处卸下的总体积，等于该趟被分配到客户 $i$ 的订单总体积：

$$
\sum_{\substack{h\in N\\ h\neq i}} g_{hikp}
-
\sum_{\substack{j\in N\\ j\neq i}} g_{ijkp}
=
\sum_{r\in R_i} v_r\alpha_{rkp},
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

且回仓时该趟剩余体积载荷为 0：

$$
g_{i0kp}=0,
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

说明：上述两组载荷流守恒约束在控制载荷传播的同时，也能隐含消除与配送中心无关的无效子回路，因此无需再单独设置额外的子回路消除约束。

---

## 7.11 软时间窗约束

不再单独设置服务指示变量，而直接由“该客户是否被该趟访问”激活时间窗约束：

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

## 7.12 趟内时变旅行时间约束

若车辆 $k$ 的第 $p$ 趟从客户 $i$ 行驶到客户 $j$，则其到达时刻满足：

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

## 7.13 趟次返回时刻约束

若车辆 $k$ 的第 $p$ 趟最后从客户 $i$ 返回配送中心，则该趟回仓时刻满足：

$$
T_{kp}^{\mathrm{ret}}
\ge
A_{ikp}+W_{ikp}+s_i+\tau_{i0}(A_{ikp}+W_{ikp}+s_i)
-B(1-x_{i0kp}),
\qquad \forall i\in C,\forall k\in K,\forall p\in P
$$

---

## 7.14 多趟时间衔接约束

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
\qquad \forall k\in K,\forall p=1,2,\dots,P_{\max}-1
$$

---

## 7.15 变量取值约束

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

## 8. 模型特点与说明

相较于未简化的多趟模型，该模型的主要特点在于：

1. **保留核心业务逻辑**  
   仍然完整描述了订单不可拆分、客户可拆可不拆、单车允许多趟、双容量、软时间窗和时变速度。

2. **减少冗余二元变量**  
   删除了客户服务指示变量和车辆启用变量，改由路径变量与第一趟启用变量间接表示。

3. **减少联动约束数量**  
   通过“订单分配与路径访问联动”替代多层服务变量联动，结构更紧凑。

4. **不再单独设置客户至少服务一次约束**  
   因为客户是否被服务已由订单唯一分配自动保证。

5. **不再单独设置子回路消除约束**  
   由于重量流和体积流守恒本身已能够抑制无效子回路。

因此，该模型可以视为一个：

$$
\text{多趟、异构、订单不可拆分、客户可分次服务的紧凑型混合整数非线性规划模型}
$$

---

## 9. 可直接用于论文的总结性表述

针对问题一，本文建立了一个“订单不可拆分、客户可分次服务、单车允许多趟”的异构绿色车辆路径优化模型。模型以订单分配、路径选择、趟次安排和弧载荷为核心决策对象，在满足订单唯一分配、客户访问与订单联动、车辆多趟出入库、车型数量、重量与体积双容量、软时间窗及时变旅行时间等约束条件下，以固定启动车辆成本、能耗成本、碳排放成本、等待成本与迟到惩罚成本之和最小为目标，求解静态环境下的最优配送调度方案。为提高模型紧凑性，本文删除了冗余的客户服务指示变量与车辆启用变量，并利用路径变量和趟次连续性约束进行替代，从而在保持建模思想基本不变的前提下有效简化了约束系统。