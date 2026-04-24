# 问题一：静态环境下的城市绿色物流配送调度模型（修正版）

## 1. 问题重述

在无政策限制条件下，物流企业需使用异构混合车队完成 98 个客户点的配送任务。  
配送过程中需要同时考虑：

- 车辆异构性；
- 车辆载重与容积双容量约束；
- 客户软时间窗约束；
- 速度时变特性；
- 能耗成本与碳排放成本。

结合原始数据特点可知：  
原始数据以**订单**为基本单位，同一客户点可能对应多个订单；部分客户的全部订单总需求可由一辆车完成，而部分客户由于总重量或总体积超出单车能力，必须由多辆车共同完成配送。因此，问题一应建立为一个：

$$
\text{订单不可拆分、客户可分次服务、异构车队、双容量约束、软时间窗、时变速度的绿色车辆路径优化模型}
$$

---

## 2. 模型假设

1. 原始数据以订单为基本单位，每个订单对应唯一客户点，且**单个订单不可拆分**。
2. 同一客户点可对应多个订单，配送路径中的服务节点仍以客户点表示。
3. 若某客户的全部订单可同时满足某类车辆的重量与体积容量约束，则该客户可以由一辆车一次完成配送；否则允许该客户由多辆车分次完成配送。
4. 是否对某客户采用单车服务或多车分次服务，不预先人为指定，而由优化模型根据容量约束、时间窗约束及总成本自动决定。
5. 每辆车对同一客户点至多访问一次；若同一客户由多辆车服务，则视为多个车辆分别到访该客户。
6. 所有车辆均从配送中心出发，并在完成配送任务后返回配送中心。
7. 每次车辆到访客户点均需进行一次服务作业，服务时间固定为 20 分钟。
8. 车辆行驶速度受交通时段影响，静态优化中采用各时段速度分布的均值构造时变旅行时间函数。
9. 软时间窗对每次车辆到访均生效；提前到达产生等待成本，延迟到达产生惩罚成本。
10. 车辆能耗由车速与载荷率共同决定，并进一步折算为能耗成本与碳排放成本。

---

## 3. 符号说明

## 3.1 集合与索引

- $C=\{1,2,\dots,n\}$：客户集合；
- $N=\{0\}\cup C$：节点集合，其中 $0$ 表示配送中心；
- $R$：订单集合；
- $R_i\subseteq R$：客户 $i$ 对应的订单集合；
- $K$：车辆集合；
- $H$：车型集合；
- $K_h\subseteq K$：车型 $h$ 对应的车辆集合；
- $K^F\subseteq K$：燃油车集合；
- $K^E\subseteq K$：新能源车集合；
- $A=\{(i,j)\mid i,j\in N,\ i\neq j\}$：可行弧集合。

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

注意：$q_i,u_i$ 仅用于统计客户总需求及构造辅助分析，不表示客户需求可以连续拆分。

### （3）车辆参数

- $Q_k$：车辆 $k$ 的最大载重（kg）；
- $U_k$：车辆 $k$ 的最大容积（m$^3$）；
- $F_k$：车辆 $k$ 的启动车辆固定成本（元）；
- $n_h$：车型 $h$ 的可用车辆数量。

### （4）路网与时间参数

- $d_{ij}$：节点 $i$ 到节点 $j$ 的道路距离（km）；
- $\bar v(t)$：时刻 $t$ 对应的平均速度（km/h）；
- $\tau_{ij}(t)$：车辆在时刻 $t$ 从节点 $i$ 出发到达节点 $j$ 的旅行时间（h）；
- $t_0$：配送中心统一发车时刻；
- $B$：足够大的常数（Big-M 常数）。

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

根据题意，取各时段速度分布均值构造平均速度函数：

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

若车辆跨越多个交通时段，则采用分段累计法计算。

---

## 5. 决策变量

### 5.1 订单分配变量

$$
\alpha_{rk}=
\begin{cases}
1, & \text{若订单 }r\text{ 由车辆 }k\text{ 承运} \\
0, & \text{否则}
\end{cases}
\qquad \forall r\in R,\ \forall k\in K
$$

该变量用于保证**订单不可拆分**。

### 5.2 客户—车辆服务变量

$$
\delta_{ik}=
\begin{cases}
1, & \text{若车辆 }k\text{ 到访并服务客户 }i \\
0, & \text{否则}
\end{cases}
\qquad \forall i\in C,\ \forall k\in K
$$

该变量用于表示客户 $i$ 是否由车辆 $k$ 服务。

### 5.3 路径变量

$$
x_{ijk}=
\begin{cases}
1, & \text{若车辆 }k\text{ 从节点 }i\text{ 行驶到节点 }j \\
0, & \text{否则}
\end{cases}
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

### 5.4 车辆启用变量

$$
y_k=
\begin{cases}
1, & \text{若车辆 }k\text{ 被启用} \\
0, & \text{否则}
\end{cases}
\qquad \forall k\in K
$$

### 5.5 弧载荷变量

- $f_{ijk}$：车辆 $k$ 在弧 $(i,j)$ 上承载的重量载荷（kg）；
- $g_{ijk}$：车辆 $k$ 在弧 $(i,j)$ 上承载的体积载荷（m$^3$）。

### 5.6 时间变量

- $A_{ik}$：车辆 $k$ 到达客户 $i$ 的时刻；
- $W_{ik}$：车辆 $k$ 在客户 $i$ 的等待时间；
- $L_{ik}$：车辆 $k$ 在客户 $i$ 的迟到时间。

定义离开客户 $i$ 的时刻为：

$$
D_{ik}=A_{ik}+W_{ik}+s_i
$$

---

## 6. 目标函数

问题一以总配送成本最小为目标，总成本由以下五部分组成：

1. 车辆固定启用成本；
2. 能耗成本；
3. 碳排放成本；
4. 提前到达等待成本；
5. 迟到惩罚成本。

故目标函数为：

$$
\min Z=C_{\text{fix}}+C_{\text{ene}}+C_{\text{car}}+C_{\text{wait}}+C_{\text{late}}
$$

### 6.1 固定启用成本

$$
C_{\text{fix}}=\sum_{k\in K}F_k y_k
$$

### 6.2 弧上载荷率

定义车辆 $k$ 在弧 $(i,j)$ 上的重量载荷率为：

$$
\lambda_{ijk}=\frac{f_{ijk}}{Q_k}
$$

### 6.3 燃油车弧上油耗量

若 $k\in K^F$，则弧 $(i,j)$ 上的油耗量为：

$$
\phi_{ijk}^{F}
=
\frac{d_{ij}}{100}
\cdot
FPK(\bar v(D_{ik}))
\cdot
\left(1+0.4\lambda_{ijk}\right)
$$

### 6.4 新能源车弧上电耗量

若 $k\in K^E$，则弧 $(i,j)$ 上的电耗量为：

$$
\phi_{ijk}^{E}
=
\frac{d_{ij}}{100}
\cdot
EPK(\bar v(D_{ik}))
\cdot
\left(1+0.35\lambda_{ijk}\right)
$$

### 6.5 能耗成本

$$
C_{\text{ene}}
=
\sum_{k\in K^F}\sum_{(i,j)\in A} p^F \phi_{ijk}^{F}
+
\sum_{k\in K^E}\sum_{(i,j)\in A} p^E \phi_{ijk}^{E}
$$

### 6.6 碳排放成本

$$
C_{\text{car}}
=
\sum_{k\in K^F}\sum_{(i,j)\in A} p^C\eta \phi_{ijk}^{F}
+
\sum_{k\in K^E}\sum_{(i,j)\in A} p^C\gamma \phi_{ijk}^{E}
$$

### 6.7 等待成本

$$
C_{\text{wait}}=c_w\sum_{i\in C}\sum_{k\in K}W_{ik}
$$

### 6.8 迟到惩罚成本

$$
C_{\text{late}}=c_l\sum_{i\in C}\sum_{k\in K}L_{ik}
$$

---

## 7. 约束条件

## 7.1 订单唯一分配约束

每个订单必须且只能由一辆车承运：

$$
\sum_{k\in K}\alpha_{rk}=1,
\qquad \forall r\in R
$$

该约束直接保证订单不可拆分。

---

## 7.2 订单分配与客户服务联动约束

若订单 $r$ 属于客户 $i$，且由车辆 $k$ 承运，则车辆 $k$ 必须到访客户 $i$：

$$
\alpha_{rk}\le \delta_{i(r)k},
\qquad \forall r\in R,\ \forall k\in K
$$

---

## 7.3 客户可由一个或多个车辆服务

每个客户至少被一辆车服务：

$$
\sum_{k\in K}\delta_{ik}\ge 1,
\qquad \forall i\in C
$$

该约束体现：  
有些客户可能仅由一辆车完成全部订单；有些客户则可能由多辆车共同完成配送。

---

## 7.4 客户访问与路径联动约束

若车辆 $k$ 服务客户 $i$，则该车辆必须对客户 $i$ 进一次、出一次：

$$
\sum_{\substack{j\in N\\ j\neq i}}x_{ijk}=\delta_{ik},
\qquad \forall i\in C,\ \forall k\in K
$$

$$
\sum_{\substack{j\in N\\ j\neq i}}x_{jik}=\delta_{ik},
\qquad \forall i\in C,\ \forall k\in K
$$

这组约束同时保证：  
每辆车对同一客户至多访问一次。

---

## 7.5 车辆从配送中心出发并返回约束

每辆被启用车辆从配送中心出发一次，并返回一次：

$$
\sum_{j\in C}x_{0jk}=y_k,
\qquad \forall k\in K
$$

$$
\sum_{i\in C}x_{i0k}=y_k,
\qquad \forall k\in K
$$

---

## 7.6 车型数量约束

各车型实际启用车辆数不得超过可用数量：

$$
\sum_{k\in K_h}y_k\le n_h,
\qquad \forall h\in H
$$

---

## 7.7 弧上重量容量约束

任意车辆在任意弧上的载重不得超过其最大载重：

$$
0\le f_{ijk}\le Q_k x_{ijk},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

---

## 7.8 弧上体积容量约束

任意车辆在任意弧上的体积载荷不得超过其最大容积：

$$
0\le g_{ijk}\le U_k x_{ijk},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

---

## 7.9 客户节点重量流守恒约束

车辆 $k$ 在客户 $i$ 处卸下的总重量，等于其被分配到该客户的订单总重量：

$$
\sum_{\substack{h\in N\\ h\neq i}} f_{hik}
-
\sum_{\substack{j\in N\\ j\neq i}} f_{ijk}
=
\sum_{r\in R_i} w_r \alpha_{rk},
\qquad \forall i\in C,\ \forall k\in K
$$

返回配送中心时，车辆不再携带未配送重量：

$$
f_{i0k}=0,
\qquad \forall i\in C,\ \forall k\in K
$$

---

## 7.10 客户节点体积流守恒约束

车辆 $k$ 在客户 $i$ 处卸下的总体积，等于其被分配到该客户的订单总体积：

$$
\sum_{\substack{h\in N\\ h\neq i}} g_{hik}
-
\sum_{\substack{j\in N\\ j\neq i}} g_{ijk}
=
\sum_{r\in R_i} v_r \alpha_{rk},
\qquad \forall i\in C,\ \forall k\in K
$$

返回配送中心时，车辆不再携带未配送体积：

$$
g_{i0k}=0,
\qquad \forall i\in C,\ \forall k\in K
$$

---

## 7.11 软时间窗约束

对每次客户—车辆到访，等待时间与迟到时间定义为：

$$
W_{ik}\ge a_i-A_{ik}-B(1-\delta_{ik}),
\qquad \forall i\in C,\ \forall k\in K
$$

$$
L_{ik}\ge A_{ik}-b_i-B(1-\delta_{ik}),
\qquad \forall i\in C,\ \forall k\in K
$$

$$
W_{ik}\ge 0,\qquad L_{ik}\ge 0,
\qquad \forall i\in C,\ \forall k\in K
$$

---

## 7.12 时变旅行时间约束

若车辆 $k$ 从客户 $i$ 行驶至客户 $j$，则到达时刻满足：

$$
A_{jk}
\ge
A_{ik}+W_{ik}+s_i+\tau_{ij}(A_{ik}+W_{ik}+s_i)-B(1-x_{ijk}),
\qquad \forall i,j\in C,\ i\neq j,\ \forall k\in K
$$

若客户 $j$ 是车辆 $k$ 从配送中心出发后的首个访问客户，则有：

$$
A_{jk}
\ge
t_0+\tau_{0j}(t_0)-B(1-x_{0jk}),
\qquad \forall j\in C,\ \forall k\in K
$$

---

## 7.13 变量取值约束

$$
x_{ijk}\in\{0,1\},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

$$
y_k\in\{0,1\},
\qquad \forall k\in K
$$

$$
\delta_{ik}\in\{0,1\},
\qquad \forall i\in C,\ \forall k\in K
$$

$$
\alpha_{rk}\in\{0,1\},
\qquad \forall r\in R,\ \forall k\in K
$$

$$
A_{ik}\ge 0,\quad W_{ik}\ge 0,\quad L_{ik}\ge 0,
\qquad \forall i\in C,\ \forall k\in K
$$

$$
f_{ijk}\ge 0,\quad g_{ijk}\ge 0,
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

---

## 8. 完整优化模型

综上，问题一的完整优化模型可写为：

$$
\min Z=
\sum_{k\in K}F_k y_k
+
\sum_{k\in K^F}\sum_{(i,j)\in A} p^F\phi_{ijk}^{F}
+
\sum_{k\in K^E}\sum_{(i,j)\in A} p^E\phi_{ijk}^{E}
+
\sum_{k\in K^F}\sum_{(i,j)\in A} p^C\eta\phi_{ijk}^{F}
+
\sum_{k\in K^E}\sum_{(i,j)\in A} p^C\gamma\phi_{ijk}^{E}
+
c_w\sum_{i\in C}\sum_{k\in K}W_{ik}
+
c_l\sum_{i\in C}\sum_{k\in K}L_{ik}
$$

满足以下约束：

$$
\sum_{k\in K}\alpha_{rk}=1,
\qquad \forall r\in R
$$

$$
\alpha_{rk}\le \delta_{i(r)k},
\qquad \forall r\in R,\ \forall k\in K
$$

$$
\sum_{k\in K}\delta_{ik}\ge 1,
\qquad \forall i\in C
$$

$$
\sum_{\substack{j\in N\\ j\neq i}}x_{ijk}=\delta_{ik},
\qquad \forall i\in C,\ \forall k\in K
$$

$$
\sum_{\substack{j\in N\\ j\neq i}}x_{jik}=\delta_{ik},
\qquad \forall i\in C,\ \forall k\in K
$$

$$
\sum_{j\in C}x_{0jk}=y_k,
\qquad \forall k\in K
$$

$$
\sum_{i\in C}x_{i0k}=y_k,
\qquad \forall k\in K
$$

$$
\sum_{k\in K_h}y_k\le n_h,
\qquad \forall h\in H
$$

$$
0\le f_{ijk}\le Q_k x_{ijk},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

$$
0\le g_{ijk}\le U_k x_{ijk},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

$$
\sum_{\substack{h\in N\\ h\neq i}} f_{hik}
-
\sum_{\substack{j\in N\\ j\neq i}} f_{ijk}
=
\sum_{r\in R_i} w_r \alpha_{rk},
\qquad \forall i\in C,\ \forall k\in K
$$

$$
\sum_{\substack{h\in N\\ h\neq i}} g_{hik}
-
\sum_{\substack{j\in N\\ j\neq i}} g_{ijk}
=
\sum_{r\in R_i} v_r \alpha_{rk},
\qquad \forall i\in C,\ \forall k\in K
$$

$$
f_{i0k}=0,\qquad g_{i0k}=0,
\qquad \forall i\in C,\ \forall k\in K
$$

$$
W_{ik}\ge a_i-A_{ik}-B(1-\delta_{ik}),
\qquad \forall i\in C,\ \forall k\in K
$$

$$
L_{ik}\ge A_{ik}-b_i-B(1-\delta_{ik}),
\qquad \forall i\in C,\ \forall k\in K
$$

$$
A_{jk}
\ge
A_{ik}+W_{ik}+s_i+\tau_{ij}(A_{ik}+W_{ik}+s_i)-B(1-x_{ijk}),
\qquad \forall i,j\in C,\ i\neq j,\ \forall k\in K
$$

$$
A_{jk}
\ge
t_0+\tau_{0j}(t_0)-B(1-x_{0jk}),
\qquad \forall j\in C,\ \forall k\in K
$$

$$
x_{ijk},y_k,\delta_{ik},\alpha_{rk}\in\{0,1\}
$$

$$
A_{ik},W_{ik},L_{ik},f_{ijk},g_{ijk}\ge 0
$$

---

## 9. 模型说明

该模型相较于传统客户级 VRPTW 的主要改进体现在以下几个方面：

1. **订单不可拆分**：通过订单—车辆二元分配变量 $\alpha_{rk}$ 保证每个订单完整交由一辆车承运；
2. **客户可拆可不拆**：通过客户—车辆服务变量 $\delta_{ik}$ 允许客户由一个或多个车辆服务，是否拆分由模型自动决定；
3. **双容量约束**：同时使用重量流变量 $f_{ijk}$ 和体积流变量 $g_{ijk}$ 控制载重与容积限制；
4. **时变旅行时间**：通过 $\tau_{ij}(t)$ 表征车辆出发时刻对旅行时间的影响；
5. **绿色成本机制**：在传统路径优化目标中纳入能耗成本和碳排放成本；
6. **软时间窗机制**：允许早到或晚到，但通过等待成本和惩罚成本计入总目标函数。

因此，问题一最终可表述为一个：

$$
\text{混合整数非线性规划模型（MINLP）}
$$

若后续对时变旅行时间函数与能耗函数作分段线性化处理，则可进一步转化为混合整数线性近似模型进行求解。

---

## 10. 可直接用于论文的总结性表述

针对问题一，本文建立了一个“订单不可拆分、客户可分次服务”的异构绿色车辆路径优化模型。模型以订单分配、客户服务、车辆路径和弧载荷为决策对象，在满足订单唯一分配、客户可被单车或多车服务、车辆出入库、车型数量、重量与体积双容量、软时间窗及时变旅行时间等约束条件下，以固定启动车辆成本、能耗成本、碳排放成本、等待成本与迟到惩罚成本之和最小为优化目标，从而获得静态环境下的最优配送调度方案。