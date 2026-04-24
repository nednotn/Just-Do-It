# 问题一：静态环境下的城市绿色物流配送调度模型

## 1. 问题描述

针对问题一，在无政策限制条件下，需要综合考虑车辆类型、载重与体积双约束、软时间窗约束以及速度时变特性，建立以**总配送成本最小**为目标的车辆调度优化模型。

根据题意，该问题可建模为一个**异构车队、双容量约束、软时间窗、时变旅行时间、含能耗与碳排放成本的绿色车辆路径优化问题**。

---

## 2. 模型假设

为构建封闭的数学规划模型，作如下假设：

1. 每个客户点的需求已由订单数据聚合完成，且每个客户点只能由一辆车服务一次，不允许拆分配送。？？？
2. 所有车辆均从同一配送中心出发，并在完成配送后返回配送中心。
3. 同一车型车辆的技术参数一致，包括载重、容积、能耗特性等。
4. 客户点服务时间固定，均为 20 分钟。
5. 各节点之间的距离由题目给定的距离矩阵确定，不再额外考虑路径绕行。
6. 不考虑中途加油、充电、换车和转运过程。
7. 软时间窗允许早到和晚到，但分别产生等待成本和惩罚成本。
8. 车辆行驶速度受时段影响，在静态优化阶段采用各时段速度分布的均值进行确定化处理。？？？
9. 油耗/电耗除受速度影响外，还受车辆载荷率影响，并采用线性比例方式近似刻画载重对能耗的提升。

---

## 3. 符号说明

### 3.1 集合与索引

设：

- $N=\{0,1,2,\dots,n\}$：所有节点集合，其中 $0$ 表示配送中心；
- $C=\{1,2,\dots,n\}$：客户节点集合；
- $M$：车型集合；
- $K_m$：车型 $m$ 的车辆集合；
- $K=\bigcup_{m\in M}K_m$：所有车辆集合；
- $K^F\subseteq K$：燃油车集合；
- $K^E\subseteq K$：新能源车集合；
- $A=\{(i,j)\mid i,j\in N,\ i\neq j\}$：可行弧集合。

---

### 3.2 参数定义

#### （1）客户需求与服务参数

- $q_i$：客户 $i$ 的需求重量（kg）；
- $u_i$：客户 $i$ 的需求体积（m$^3$）；
- $[a_i,b_i]$：客户 $i$ 的软时间窗，其中 $a_i$ 为最早到达时刻，$b_i$ 为最晚到达时刻；
- $s_i$：客户 $i$ 的服务时间，题中取 $20$ 分钟，即 $\frac{1}{3}$ 小时。

#### （2）车辆参数

- $Q_k$：车辆 $k$ 的最大载重（kg）；
- $U_k$：车辆 $k$ 的最大容积（m$^3$）；
- $f_k$：车辆 $k$ 的启动车辆固定成本，题中取 $400$ 元；
- $n_m$：车型 $m$ 的可用车辆数。

#### （3）路径与时间参数

- $d_{ij}$：节点 $i$ 到节点 $j$ 的道路距离（km）；
- $\bar v(t)$：时刻 $t$ 对应的平均行驶速度（km/h）；
- $\tau_{ij}(t)$：车辆在时刻 $t$ 从节点 $i$ 出发驶向节点 $j$ 的旅行时间（h）；
- $t_0$：配送中心统一发车时刻；
- $M$：充分大的正数，用于 Big-M 线性化。

#### （4）成本参数

- $c_w=20$：单位等待成本（元/h）；
- $c_l=50$：单位迟到惩罚成本（元/h）；
- $p^F=7.61$：燃油价格（元/L）；
- $p^E=1.64$：电价（元/(kW$\cdot$h)）；
- $p^C=0.65$：单位碳排放成本（元/kg）。

#### （5）能耗与碳排放参数

燃油车百公里油耗函数为：

$$
FPK(v)=0.0025v^2-0.2554v+31.75
$$

新能源车百公里电耗函数为：

$$
EPK(v)=0.0014v^2-0.12v+36.19
$$

满载附加系数：

- 燃油车：满载较空载能耗提高 $40\%$；
- 新能源车：满载较空载能耗提高 $35\%$。

碳排放系数：

- 燃油车：$\eta=2.547$ kg/L；
- 新能源车：$\gamma=0.501$ kg/(kW$\cdot$h)。

---

## 4. 时变速度函数

根据题意，将全天划分为不同交通状态时段，并取各时段速度分布均值构造确定性平均速度函数：

$$
\bar v(t)=
\begin{cases}
9.8, & t\in [8{:}00,9{:}00)\cup[11{:}30,13{:}00) \\
35.4, & t\in [10{:}00,11{:}30)\cup[15{:}00,17{:}00) \\
55.3, & t\in [9{:}00,10{:}00)\cup[13{:}00,15{:}00)
\end{cases}
$$

进一步定义时变旅行时间函数：

$$
\tau_{ij}(t)=\text{车辆在时刻 }t\text{ 从节点 }i\text{ 出发到达节点 }j\text{ 所需的总行驶时间}
$$

该函数可通过分段累计法预处理得到，即若车辆跨越多个时段，则分段计算其在不同速度区间内的行驶时间并求和。

---

## 5. 决策变量

### 5.1 路径决策变量

$$
x_{ijk}=
\begin{cases}
1, & \text{若车辆 }k\text{ 从节点 }i\text{ 行驶到节点 }j \\
0, & \text{否则}
\end{cases}
\qquad (i,j)\in A,\ k\in K
$$

### 5.2 车辆启用变量

$$
y_k=
\begin{cases}
1, & \text{若车辆 }k\text{ 被启用} \\
0, & \text{否则}
\end{cases}
\qquad k\in K
$$

### 5.3 时间变量

- $A_i$：车辆到达客户 $i$ 的时刻；
- $W_i$：客户 $i$ 的等待时间；
- $L_i$：客户 $i$ 的迟到时间。

定义客户 $i$ 的离开时刻为：

$$
D_i=A_i+W_i+s_i
$$

### 5.4 载荷流变量

- $z_{ijk}$：车辆 $k$ 在弧 $(i,j)$ 上承载的重量载荷（kg）；
- $g_{ijk}$：车辆 $k$ 在弧 $(i,j)$ 上承载的体积载荷（m$^3$）。

---

## 6. 目标函数

问题一以总配送成本最小为目标，总成本由以下五部分构成：

1. 车辆固定启用成本；
2. 能耗成本；
3. 碳排放成本；
4. 早到等待成本；
5. 晚到惩罚成本。

因此目标函数为：

$$
\min Z=C_{\text{fix}}+C_{\text{ene}}+C_{\text{car}}+C_{\text{wait}}+C_{\text{late}}
$$

---

### 6.1 固定启用成本

$$
C_{\text{fix}}=\sum_{k\in K}f_k y_k
$$

---

### 6.2 弧上载荷率

定义车辆 $k$ 在弧 $(i,j)$ 上的重量载荷率为：

$$
\lambda_{ijk}=\frac{z_{ijk}}{Q_k}
$$

---

### 6.3 燃油车弧上油耗量

若 $k\in K^F$，则车辆 $k$ 在弧 $(i,j)$ 上的油耗量为：

$$
\phi_{ijk}^{F}
=
\frac{d_{ij}}{100}
\cdot
FPK(\bar v(D_i))
\cdot
\left(1+0.4\lambda_{ijk}\right)
$$

展开后可写为：

$$
\phi_{ijk}^{F}
=
\frac{d_{ij}}{100}
\left(0.0025\bar v(D_i)^2-0.2554\bar v(D_i)+31.75\right)
\left(1+0.4\lambda_{ijk}\right)
$$

---

### 6.4 新能源车弧上电耗量

若 $k\in K^E$，则车辆 $k$ 在弧 $(i,j)$ 上的电耗量为：

$$
\phi_{ijk}^{E}
=
\frac{d_{ij}}{100}
\cdot
EPK(\bar v(D_i))
\cdot
\left(1+0.35\lambda_{ijk}\right)
$$

展开后可写为：

$$
\phi_{ijk}^{E}
=
\frac{d_{ij}}{100}
\left(0.0014\bar v(D_i)^2-0.12\bar v(D_i)+36.19\right)
\left(1+0.35\lambda_{ijk}\right)
$$

---

### 6.5 能耗成本

$$
C_{\text{ene}}
=
\sum_{k\in K^F}\sum_{(i,j)\in A} p^F\phi_{ijk}^{F}
+
\sum_{k\in K^E}\sum_{(i,j)\in A} p^E\phi_{ijk}^{E}
$$

---

### 6.6 碳排放成本

燃油车弧上碳排放成本为：

$$
p^C\eta \phi_{ijk}^{F}
$$

新能源车弧上碳排放成本为：

$$
p^C\gamma \phi_{ijk}^{E}
$$

故总碳排放成本为：

$$
C_{\text{car}}
=
\sum_{k\in K^F}\sum_{(i,j)\in A} p^C\eta\phi_{ijk}^{F}
+
\sum_{k\in K^E}\sum_{(i,j)\in A} p^C\gamma\phi_{ijk}^{E}
$$

---

### 6.7 等待成本

$$
C_{\text{wait}}=c_w\sum_{i\in C}W_i
$$

### 6.8 迟到惩罚成本

$$
C_{\text{late}}=c_l\sum_{i\in C}L_i
$$

---

## 7. 约束条件

### 7.1 客户唯一服务约束

每个客户必须且仅能被一辆车访问一次：

$$
\sum_{k\in K}\sum_{\substack{i\in N\\ i\neq j}}x_{ijk}=1,
\qquad \forall j\in C
$$

---

### 7.2 车辆从配送中心出发并返回约束

每辆被启用的车辆从配送中心出发一次，并返回一次：

$$
\sum_{j\in C}x_{0jk}=y_k,
\qquad \forall k\in K
$$

$$
\sum_{i\in C}x_{i0k}=y_k,
\qquad \forall k\in K
$$

---

### 7.3 车辆流守恒约束

对任一客户节点，进入该点的车辆必须离开该点：

$$
\sum_{\substack{i\in N\\ i\neq h}}x_{ihk}
=
\sum_{\substack{j\in N\\ j\neq h}}x_{hjk},
\qquad \forall h\in C,\ \forall k\in K
$$

---

### 7.4 车型数量约束

各车型实际启用车辆数不能超过可用数量：

$$
\sum_{k\in K_m}y_k\le n_m,
\qquad \forall m\in M
$$

---

### 7.5 重量容量约束

弧上重量流不超过车辆最大载重：

$$
0\le z_{ijk}\le Q_kx_{ijk},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

客户节点处满足重量流守恒：

$$
\sum_{\substack{h\in N\\ h\neq i}}z_{hik}
-
\sum_{\substack{j\in N\\ j\neq i}}z_{ijk}
=
q_i\sum_{\substack{h\in N\\ h\neq i}}x_{hik},
\qquad \forall i\in C,\ \forall k\in K
$$

回到配送中心时载重应为零：

$$
z_{i0k}=0,
\qquad \forall i\in C,\ \forall k\in K
$$

---

### 7.6 体积容量约束

弧上体积流不超过车辆最大容积：

$$
0\le g_{ijk}\le U_kx_{ijk},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

客户节点处满足体积流守恒：

$$
\sum_{\substack{h\in N\\ h\neq i}}g_{hik}
-
\sum_{\substack{j\in N\\ j\neq i}}g_{ijk}
=
u_i\sum_{\substack{h\in N\\ h\neq i}}x_{hik},
\qquad \forall i\in C,\ \forall k\in K
$$

回到配送中心时体积载荷应为零：

$$
g_{i0k}=0,
\qquad \forall i\in C,\ \forall k\in K
$$

---

### 7.7 软时间窗约束

等待时间定义为：

$$
W_i\ge a_i-A_i,
\qquad \forall i\in C
$$

迟到时间定义为：

$$
L_i\ge A_i-b_i,
\qquad \forall i\in C
$$

非负约束：

$$
W_i\ge 0,\qquad L_i\ge 0,
\qquad \forall i\in C
$$

---

### 7.8 时变旅行时间约束

若车辆从客户 $i$ 行驶到客户 $j$，则其到达时刻必须满足时序关系：

$$
A_j
\ge
A_i+W_i+s_i+\tau_{ij}(A_i+W_i+s_i)
-
M\left(1-\sum_{k\in K}x_{ijk}\right),
\qquad \forall i,j\in C,\ i\neq j
$$

若客户 $j$ 是某辆车从配送中心出发后的首个访问节点，则有：

$$
A_j
\ge
t_0+\tau_{0j}(t_0)
-
M\left(1-\sum_{k\in K}x_{0jk}\right),
\qquad \forall j\in C
$$

---

### 7.9 变量取值约束

$$
x_{ijk}\in\{0,1\},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

$$
y_k\in\{0,1\},
\qquad \forall k\in K
$$

$$
A_i\ge 0,\quad W_i\ge 0,\quad L_i\ge 0,
\qquad \forall i\in C
$$

$$
z_{ijk}\ge 0,\quad g_{ijk}\ge 0,
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

---

## 8. 完整优化模型

综上，问题一的完整数学模型可写为：

$$
\min Z=
\sum_{k\in K}f_k y_k
+
\sum_{k\in K^F}\sum_{(i,j)\in A}(p^F+p^C\eta)\phi_{ijk}^{F}
+
\sum_{k\in K^E}\sum_{(i,j)\in A}(p^E+p^C\gamma)\phi_{ijk}^{E}
+
c_w\sum_{i\in C}W_i
+
c_l\sum_{i\in C}L_i
$$

满足：

$$
\sum_{k\in K}\sum_{\substack{i\in N\\ i\neq j}}x_{ijk}=1,
\qquad \forall j\in C
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
\sum_{\substack{i\in N\\ i\neq h}}x_{ihk}
=
\sum_{\substack{j\in N\\ j\neq h}}x_{hjk},
\qquad \forall h\in C,\ \forall k\in K
$$

$$
\sum_{k\in K_m}y_k\le n_m,
\qquad \forall m\in M
$$

$$
0\le z_{ijk}\le Q_kx_{ijk},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

$$
\sum_{\substack{h\in N\\ h\neq i}}z_{hik}
-
\sum_{\substack{j\in N\\ j\neq i}}z_{ijk}
=
q_i\sum_{\substack{h\in N\\ h\neq i}}x_{hik},
\qquad \forall i\in C,\ \forall k\in K
$$

$$
z_{i0k}=0,
\qquad \forall i\in C,\ \forall k\in K
$$

$$
0\le g_{ijk}\le U_kx_{ijk},
\qquad \forall (i,j)\in A,\ \forall k\in K
$$

$$
\sum_{\substack{h\in N\\ h\neq i}}g_{hik}
-
\sum_{\substack{j\in N\\ j\neq i}}g_{ijk}
=
u_i\sum_{\substack{h\in N\\ h\neq i}}x_{hik},
\qquad \forall i\in C,\ \forall k\in K
$$

$$
g_{i0k}=0,
\qquad \forall i\in C,\ \forall k\in K
$$

$$
W_i\ge a_i-A_i,
\qquad \forall i\in C
$$

$$
L_i\ge A_i-b_i,
\qquad \forall i\in C
$$

$$
A_j
\ge
A_i+W_i+s_i+\tau_{ij}(A_i+W_i+s_i)
-
M\left(1-\sum_{k\in K}x_{ijk}\right),
\qquad \forall i,j\in C,\ i\neq j
$$

$$
A_j
\ge
t_0+\tau_{0j}(t_0)
-
M\left(1-\sum_{k\in K}x_{0jk}\right),
\qquad \forall j\in C
$$

$$
x_{ijk}\in\{0,1\},\quad y_k\in\{0,1\}
$$

$$
A_i\ge 0,\quad W_i\ge 0,\quad L_i\ge 0
$$

$$
z_{ijk}\ge 0,\quad g_{ijk}\ge 0
$$

---

## 9. 模型说明

该模型具有如下特点：

1. **异构车队特征**：不同车型具有不同的载重、容积和能源属性；
2. **双容量约束**：同时考虑重量和体积两个维度的运输能力限制；
3. **软时间窗机制**：允许早到或晚到，但通过成本进行惩罚；
4. **时变旅行时间机制**：车辆行驶时间由出发时刻决定，体现交通状态变化；
5. **绿色物流属性**：目标函数不仅考虑运营成本，也纳入了能耗成本和碳排放成本。

因此，问题一最终可归结为一个**混合整数非线性规划模型（MINLP）**。若后续对旅行时间函数和能耗函数进行分段线性化，则可进一步转化为**混合整数线性规划近似模型（MILP）**。

---

## 10. 可直接用于论文的总结性表述

针对问题一，建立了一个以总配送成本最小为目标的异构绿色车辆路径优化模型。模型以车辆路径选择、车辆启用、客户到达时刻及弧载荷流为决策变量，在满足客户唯一服务、车辆出入库、流守恒、车型数量、重量与体积双容量、软时间窗及时变旅行时间等约束条件下，综合优化固定启动车辆成本、能耗成本、碳排放成本、等待成本与迟到惩罚成本，从而得到静态环境下的最优配送调度方案。