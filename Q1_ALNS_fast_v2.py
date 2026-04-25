#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
python Q1_ALNS_fast_v2.py `
  --orders "附件\订单信息_处理完成.xlsx" `
  --distance "附件\距离矩阵.xlsx" `
  --time_windows "附件\时间窗.xlsx" `
  --output "results_q1_v2" `
  --iterations 10000 `
  --seed 42 `
  --log_every 20 `
  --candidate_trips 30 `
  --candidate_positions 6 `
  --min_remove 10 `
  --max_remove 50 `
  --max_return "22:00" `
  --late_insert_weight 8 `
  --trip_insert_penalty 150
'''

"""
Q1_ALNS_fast_v2.py

快速修正版 ALNS 求解器：问题一城市绿色物流配送调度。

建模口径：
1. 订单不可拆分；
2. 客户可由单车或多车、多趟服务；
3. 单车允许最多 Pmax 趟；
4. 同时考虑重量与体积容量；
5. 软时间窗、时变速度、能耗成本、碳排放成本；
6. 17:00 之后速度按一般时段 35.4 km/h 外推。

相比之前版本，本版的主要加速点：
- 插入评价采用近似增量距离，不再对每个候选位置都 deep copy + 全局 evaluate；
- 修复阶段只在有限候选趟次与有限插入位置中搜索；
- ALNS 每轮只对候选完整解做一次全局评价；
- 默认关闭计算开销较大的 worst-destroy；
- 输出仍保留车辆方案、路径、到达时间、订单分配和成本构成。
- v2 修正：插入评价显式考虑迟到、回仓超时和新车/新趟次选择，避免“少量车辆跑满 10 趟”导致迟到成本爆炸。
"""

import argparse
import copy
import json
import math
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


# ============================================================
# 1. 数据结构
# ============================================================

@dataclass(frozen=True)
class Order:
    oid: int
    customer: int
    weight: float
    volume: float


@dataclass(frozen=True)
class VehicleType:
    name: str
    energy_type: str
    cap_weight: float
    cap_volume: float
    count: int
    fixed_cost: float = 400.0


@dataclass(frozen=True)
class Vehicle:
    vid: str
    type_name: str
    energy_type: str
    cap_weight: float
    cap_volume: float
    fixed_cost: float


@dataclass
class Trip:
    route: List[int] = field(default_factory=list)   # 客户访问顺序，不含 0
    orders: List[int] = field(default_factory=list)  # 本趟承运订单编号
    load_weight: float = 0.0
    load_volume: float = 0.0


@dataclass
class Solution:
    trips: Dict[str, List[Trip]] = field(default_factory=dict)

    def copy(self) -> "Solution":
        return copy.deepcopy(self)

    def active_vehicle_ids(self) -> List[str]:
        return [vid for vid, ts in self.trips.items() if any(t.orders for t in ts)]

    def active_trips(self) -> List[Tuple[str, int, Trip]]:
        out = []
        for vid, ts in self.trips.items():
            for idx, t in enumerate(ts):
                if t.orders:
                    out.append((vid, idx, t))
        return out


@dataclass(frozen=True)
class InsertionMove:
    vehicle_id: str
    trip_idx: int
    position: Optional[int]
    is_new_trip: bool
    approx_score: float


# ============================================================
# 2. 问题数据
# ============================================================

class ProblemData:
    def __init__(
        self,
        orders: Dict[int, Order],
        vehicles: Dict[str, Vehicle],
        dist: Dict[Tuple[int, int], float],
        time_windows: Dict[int, Tuple[float, float]],
        t0_min: float = 8 * 60,
        service_min: float = 20.0,
        reload_min: float = 20.0,
        pmax: int = 2,                                 # =========================================================================
        wait_cost_per_h: float = 20.0,
        late_cost_per_h: float = 50.0,
        fuel_price: float = 7.61,
        elec_price: float = 1.64,
        carbon_price: float = 0.65,
        eta_fuel: float = 2.547,
        gamma_elec: float = 0.501,
        max_return_min: Optional[float] = 22 * 60,
        max_return_penalty_per_h: float = 5000.0,
        trip_insert_penalty: float = 150.0,
        late_insert_weight: float = 8.0,
    ):
        self.orders = orders
        self.vehicles = vehicles
        self.dist = dist
        self.time_windows = time_windows
        self.t0_min = t0_min
        self.service_min = service_min
        self.reload_min = reload_min
        self.pmax = pmax
        self.wait_cost_per_h = wait_cost_per_h
        self.late_cost_per_h = late_cost_per_h
        self.fuel_price = fuel_price
        self.elec_price = elec_price
        self.carbon_price = carbon_price
        self.eta_fuel = eta_fuel
        self.gamma_elec = gamma_elec
        self.max_return_min = max_return_min
        self.max_return_penalty_per_h = max_return_penalty_per_h
        self.trip_insert_penalty = trip_insert_penalty
        self.late_insert_weight = late_insert_weight

        self.customer_orders: Dict[int, List[int]] = defaultdict(list)
        for oid, o in self.orders.items():
            self.customer_orders[o.customer].append(oid)

        # 用于快速候选筛选：客户所属订单总量、客户最晚时间等
        self.customers = sorted(self.customer_orders.keys())

    @staticmethod
    def speed_kmph(t_min: float) -> float:
        t = t_min % (24 * 60)
        if 8 * 60 <= t < 9 * 60:
            return 9.8
        if 9 * 60 <= t < 10 * 60:
            return 55.3
        if 10 * 60 <= t < 11 * 60 + 30:
            return 35.4
        if 11 * 60 + 30 <= t < 13 * 60:
            return 9.8
        if 13 * 60 <= t < 15 * 60:
            return 55.3
        if 15 * 60 <= t < 24 * 60:
            return 35.4
        return 35.4

    @staticmethod
    def next_speed_boundary(t_min: float) -> float:
        day = math.floor(t_min / (24 * 60))
        t = t_min - day * 24 * 60
        boundaries = [8 * 60, 9 * 60, 10 * 60, 11 * 60 + 30, 13 * 60, 15 * 60, 24 * 60]
        for b in boundaries:
            if t < b:
                return day * 24 * 60 + b
        return (day + 1) * 24 * 60

    def distance(self, i: int, j: int) -> float:
        if (i, j) in self.dist:
            return self.dist[(i, j)]
        if (j, i) in self.dist:
            return self.dist[(j, i)]
        raise KeyError(f"距离矩阵中缺少节点对 ({i}, {j})")

    def travel_time_min(self, i: int, j: int, depart_min: float) -> float:
        d = self.distance(i, j)
        if d <= 0:
            return 0.0
        remaining = d
        t = depart_min
        guard = 0
        while remaining > 1e-9:
            guard += 1
            if guard > 100:
                return d / self.speed_kmph(depart_min) * 60.0
            v = self.speed_kmph(t)
            end = self.next_speed_boundary(t)
            available_min = max(end - t, 1e-6)
            can_go = v * available_min / 60.0
            if can_go >= remaining:
                return (t - depart_min) + remaining / v * 60.0
            remaining -= can_go
            t = end
        return t - depart_min

    @staticmethod
    def fpk(v: float) -> float:
        return 0.0025 * v * v - 0.2554 * v + 31.75

    @staticmethod
    def epk(v: float) -> float:
        return 0.0014 * v * v - 0.12 * v + 36.19

    def arc_energy_and_carbon(self, vehicle: Vehicle, i: int, j: int, depart_min: float, load_weight: float) -> Tuple[float, float, float]:
        d = self.distance(i, j)
        if d <= 0:
            return 0.0, 0.0, 0.0
        v = self.speed_kmph(depart_min)
        load_rate = max(0.0, min(1.0, load_weight / vehicle.cap_weight))
        if vehicle.energy_type == "fuel":
            liters = d / 100.0 * self.fpk(v) * (1.0 + 0.4 * load_rate)
            energy_cost = liters * self.fuel_price
            carbon_kg = liters * self.eta_fuel
        else:
            kwh = d / 100.0 * self.epk(v) * (1.0 + 0.35 * load_rate)
            energy_cost = kwh * self.elec_price
            carbon_kg = kwh * self.gamma_elec
        return energy_cost, carbon_kg * self.carbon_price, carbon_kg

    def check_order_feasibility(self) -> None:
        bad = []
        for o in self.orders.values():
            ok = any(o.weight <= v.cap_weight + 1e-9 and o.volume <= v.cap_volume + 1e-9 for v in self.vehicles.values())
            if not ok:
                bad.append((o.oid, o.customer, o.weight, o.volume))
        if bad:
            msg = "存在单个订单超过所有车型容量，订单不可拆分假设下实例不可行：\n"
            msg += "\n".join(map(str, bad[:20]))
            if len(bad) > 20:
                msg += f"\n... 共 {len(bad)} 个不可行订单"
            raise ValueError(msg)


# ============================================================
# 3. 数据读取
# ============================================================

def _norm_col(s: Any) -> str:
    return str(s).strip().replace(" ", "").replace("\n", "").lower()


def find_col(df: pd.DataFrame, candidates: Iterable[str]) -> str:
    norm_map = {_norm_col(c): c for c in df.columns}
    for cand in candidates:
        key = _norm_col(cand)
        if key in norm_map:
            return norm_map[key]
    for key, col in norm_map.items():
        for cand in candidates:
            ck = _norm_col(cand)
            if ck in key or key in ck:
                return col
    raise KeyError(f"未找到列名，候选={list(candidates)}，实际列={list(df.columns)}")


def normalize_node_id(x: Any) -> int:
    if pd.isna(x):
        raise ValueError("节点编号为空")
    s = str(x).strip()
    if s in {"配送中心", "中心", "depot", "Depot", "仓库"}:
        return 0
    for token in ["客户", "点", "node", "Node"]:
        s = s.replace(token, "")
    try:
        return int(float(s))
    except Exception as exc:
        raise ValueError(f"无法解析节点编号: {x}") from exc


def parse_time_to_min(x: Any) -> float:
    if pd.isna(x):
        raise ValueError("时间为空")
    if isinstance(x, pd.Timestamp):
        return float(x.hour * 60 + x.minute + x.second / 60)
    if hasattr(x, "hour") and hasattr(x, "minute"):
        return float(x.hour * 60 + x.minute + getattr(x, "second", 0) / 60)
    if isinstance(x, (int, float, np.integer, np.floating)):
        val = float(x)
        if 0 <= val < 1:
            return val * 24 * 60
        if val > 24:
            return val
        return val * 60
    s = str(x).strip()
    if ":" in s:
        parts = s.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        sec = int(parts[2]) if len(parts) > 2 else 0
        return h * 60 + m + sec / 60
    return float(s)


def min_to_hhmm(t: float) -> str:
    if t is None or not np.isfinite(t):
        return ""
    t = int(round(t))
    h = (t // 60) % 24
    m = t % 60
    day = t // (24 * 60)
    if day > 0:
        return f"D+{day} {h:02d}:{m:02d}"
    return f"{h:02d}:{m:02d}"


def load_orders(path: str) -> Dict[int, Order]:
    df = pd.read_excel(path)
    c_oid = find_col(df, ["订单编号", "订单id", "order_id", "id"])
    c_w = find_col(df, ["重量", "weight", "w"])
    c_v = find_col(df, ["体积", "volume", "v"])
    c_cust = find_col(df, ["目标客户编号", "客户编号", "customer", "customer_id"])
    orders: Dict[int, Order] = {}
    for _, row in df.iterrows():
        oid = int(row[c_oid])
        orders[oid] = Order(
            oid=oid,
            customer=normalize_node_id(row[c_cust]),
            weight=float(row[c_w]),
            volume=float(row[c_v]),
        )
    return orders


def load_time_windows(path: str) -> Dict[int, Tuple[float, float]]:
    df = pd.read_excel(path)
    c_id = find_col(df, ["客户编号", "目标客户编号", "customer", "customer_id", "节点编号"])
    c_start = find_col(df, ["最早", "开始", "earliest", "start", "起始时间", "最早到达时间"])
    c_end = find_col(df, ["最晚", "结束", "latest", "end", "终止时间", "最晚到达时间"])
    tw: Dict[int, Tuple[float, float]] = {}
    for _, row in df.iterrows():
        cid = normalize_node_id(row[c_id])
        if cid == 0:
            continue
        tw[cid] = (parse_time_to_min(row[c_start]), parse_time_to_min(row[c_end]))
    return tw


def load_distance_matrix(path: str, unit: str = "auto") -> Dict[Tuple[int, int], float]:
    df = pd.read_excel(path, header=0)
    first_col = df.columns[0]
    if len(set(df[first_col].dropna())) == len(df[first_col].dropna()):
        df2 = df.set_index(first_col)
    else:
        df2 = df.copy()
        df2.index = df2.index.astype(int)
    df2 = df2.dropna(axis=1, how="all").dropna(axis=0, how="all")
    row_ids = [normalize_node_id(x) for x in df2.index]
    col_ids = [normalize_node_id(x) for x in df2.columns]
    raw_vals = []
    dist: Dict[Tuple[int, int], float] = {}
    for ii, i in enumerate(row_ids):
        for jj, j in enumerate(col_ids):
            val = df2.iloc[ii, jj]
            if pd.isna(val):
                continue
            d = float(val)
            dist[(i, j)] = d
            if i != j and d > 0:
                raw_vals.append(d)

    # 自动识别距离单位：若正距离中位数明显大于城市公里尺度，则按米转公里。
    scale = 1.0
    unit = str(unit).lower()
    if unit == "m":
        scale = 1.0 / 1000.0
    elif unit == "km":
        scale = 1.0
    elif unit == "auto":
        med = float(np.median(raw_vals)) if raw_vals else 0.0
        if med > 200.0:
            scale = 1.0 / 1000.0
    else:
        raise ValueError("--distance_unit 只能为 auto、km 或 m")

    if scale != 1.0:
        dist = {k: v * scale for k, v in dist.items()}
    return dist

def build_vehicles() -> Dict[str, Vehicle]:
    types = [
        VehicleType("F_3000_13.5", "fuel", 3000.0, 13.5, 60),
        VehicleType("F_1500_10.8", "fuel", 1500.0, 10.8, 50),
        VehicleType("F_1250_6.5", "fuel", 1250.0, 6.5, 50),
        VehicleType("E_3000_15", "ev", 3000.0, 15.0, 10),
        VehicleType("E_1250_8.5", "ev", 1250.0, 8.5, 15),
    ]
    vehicles: Dict[str, Vehicle] = {}
    # 排序会影响初始解，EV 优先，随后容量从小到大，便于较低能耗和较高装载率。
    for vt in types:
        for idx in range(1, vt.count + 1):
            vid = f"{vt.name}_{idx:03d}"
            vehicles[vid] = Vehicle(vid, vt.name, vt.energy_type, vt.cap_weight, vt.cap_volume, vt.fixed_cost)
    return vehicles


def load_problem(args: argparse.Namespace) -> ProblemData:
    orders = load_orders(args.orders)
    tw = load_time_windows(args.time_windows)
    dist = load_distance_matrix(args.distance, unit=args.distance_unit)
    vehicles = build_vehicles()
    max_return_min = None
    if str(args.max_return).strip().lower() not in {"", "none", "no", "false"}:
        max_return_min = parse_time_to_min(args.max_return)
    data = ProblemData(
        orders=orders,
        vehicles=vehicles,
        dist=dist,
        time_windows=tw,
        t0_min=parse_time_to_min(args.t0),
        service_min=args.service_min,
        reload_min=args.reload_min,
        pmax=args.pmax,
        max_return_min=max_return_min,
        max_return_penalty_per_h=args.max_return_penalty_per_h,
        trip_insert_penalty=args.trip_insert_penalty,
        late_insert_weight=args.late_insert_weight,
    )
    data.check_order_feasibility()
    missing_tw = sorted(set(o.customer for o in orders.values()) - set(tw))
    if missing_tw:
        raise ValueError(f"时间窗文件缺少这些客户编号: {missing_tw[:30]}")
    return data


# ============================================================
# 4. 解操作与快速插入
# ============================================================

def remove_empty_trips(sol: Solution) -> None:
    for vid in list(sol.trips.keys()):
        sol.trips[vid] = [t for t in sol.trips[vid] if t.orders]
        if not sol.trips[vid]:
            del sol.trips[vid]


def active_or_candidate_vehicle_ids(problem: ProblemData, sol: Solution) -> List[str]:
    ids = set(sol.active_vehicle_ids())
    used = set(ids)
    # 每个车型取一个未启用候选车，避免候选集合过大。
    by_type_added = set()
    vehicle_list = sorted(
        problem.vehicles.values(),
        key=lambda v: (0 if v.energy_type == "ev" else 1, v.cap_weight, v.cap_volume, v.vid),
    )
    for v in vehicle_list:
        if v.vid in used:
            continue
        if v.type_name not in by_type_added:
            ids.add(v.vid)
            by_type_added.add(v.type_name)
    return list(ids)


def assigned_order_ids(sol: Solution) -> set:
    out = set()
    for _, _, trip in sol.active_trips():
        out.update(trip.orders)
    return out


def trip_customer_orders(problem: ProblemData, trip: Trip) -> Dict[int, List[int]]:
    mp = defaultdict(list)
    for oid in trip.orders:
        mp[problem.orders[oid].customer].append(oid)
    return dict(mp)


def capacity_ok(vehicle: Vehicle, trip: Trip, order: Optional[Order] = None) -> bool:
    w = trip.load_weight + (order.weight if order else 0.0)
    v = trip.load_volume + (order.volume if order else 0.0)
    return w <= vehicle.cap_weight + 1e-9 and v <= vehicle.cap_volume + 1e-9



def clone_trip(t: Trip) -> Trip:
    return Trip(route=list(t.route), orders=list(t.orders), load_weight=float(t.load_weight), load_volume=float(t.load_volume))


def simulate_trip_cost(problem: ProblemData, vehicle: Vehicle, trip: Trip, dep_min: float) -> Dict[str, float]:
    """模拟单趟的行驶、服务、等待、迟到、能耗和回仓时间。"""
    route = list(trip.route)
    by_cust = trip_customer_orders(problem, trip)
    # 防止路径遗漏有订单的客户。
    for c in by_cust:
        if c not in route:
            route.append(c)

    load_w = trip.load_weight
    cur = 0
    t = dep_min
    energy = carbon_cost = carbon_kg = wait_cost = late_cost = dist = 0.0

    for cust in route:
        d = problem.distance(cur, cust)
        e_cost, c_cost, c_kg = problem.arc_energy_and_carbon(vehicle, cur, cust, t, load_w)
        travel = problem.travel_time_min(cur, cust, t)
        arr = t + travel
        a, b = problem.time_windows[cust]
        wait = max(0.0, a - arr)
        late = max(0.0, arr - b)
        depart = arr + wait + problem.service_min

        energy += e_cost
        carbon_cost += c_cost
        carbon_kg += c_kg
        wait_cost += wait / 60.0 * problem.wait_cost_per_h
        late_cost += late / 60.0 * problem.late_cost_per_h
        dist += d

        delivered = by_cust.get(cust, [])
        load_w -= sum(problem.orders[oid].weight for oid in delivered)
        cur = cust
        t = depart

    d = problem.distance(cur, 0)
    e_cost, c_cost, c_kg = problem.arc_energy_and_carbon(vehicle, cur, 0, t, max(0.0, load_w))
    travel = problem.travel_time_min(cur, 0, t)
    ret = t + travel

    energy += e_cost
    carbon_cost += c_cost
    carbon_kg += c_kg
    dist += d

    overtime_cost = 0.0
    overtime_min = 0.0
    if problem.max_return_min is not None and ret > problem.max_return_min:
        overtime_min = ret - problem.max_return_min
        overtime_cost = overtime_min / 60.0 * problem.max_return_penalty_per_h

    return {
        "ret": ret,
        "distance": dist,
        "energy_cost": energy,
        "carbon_cost": carbon_cost,
        "carbon_kg": carbon_kg,
        "wait_cost": wait_cost,
        "late_cost": late_cost,
        "overtime_cost": overtime_cost,
        "overtime_min": overtime_min,
        "total": energy + carbon_cost + wait_cost + late_cost + overtime_cost,
    }


def vehicle_sequence_cost(problem: ProblemData, vid: str, trips: List[Trip]) -> Dict[str, float]:
    """模拟某辆车所有趟次的串行执行成本，不含车辆固定启用成本。"""
    vehicle = problem.vehicles[vid]
    active = [t for t in trips if t.orders]
    prev_ret = None
    total = energy = carbon_cost = carbon_kg = wait_cost = late_cost = overtime_cost = dist = 0.0
    ret_last = problem.t0_min
    for trip in active:
        dep = problem.t0_min if prev_ret is None else prev_ret + problem.reload_min
        ev = simulate_trip_cost(problem, vehicle, trip, dep)
        prev_ret = ev["ret"]
        ret_last = ev["ret"]
        total += ev["total"]
        energy += ev["energy_cost"]
        carbon_cost += ev["carbon_cost"]
        carbon_kg += ev["carbon_kg"]
        wait_cost += ev["wait_cost"]
        late_cost += ev["late_cost"]
        overtime_cost += ev["overtime_cost"]
        dist += ev["distance"]
    return {
        "total": total,
        "energy_cost": energy,
        "carbon_cost": carbon_cost,
        "carbon_kg": carbon_kg,
        "wait_cost": wait_cost,
        "late_cost": late_cost,
        "overtime_cost": overtime_cost,
        "distance": dist,
        "last_return": ret_last,
        "trips": len(active),
    }


def insertion_delta_score(
    problem: ProblemData,
    sol: Solution,
    vid: str,
    trip_idx: int,
    order: Order,
    pos: Optional[int],
    is_new: bool,
) -> float:
    """
    v2 插入评分：对受影响车辆做局部串行模拟。
    评分显式放大迟到增量，并对新开趟加入轻微启发式惩罚，
    从而避免少数车辆反复跑满 Pmax 导致大面积迟到。
    """
    vehicle = problem.vehicles[vid]
    old_trips = [clone_trip(t) for t in sol.trips.get(vid, []) if t.orders]
    old_cost = vehicle_sequence_cost(problem, vid, old_trips)

    new_trips = [clone_trip(t) for t in old_trips]
    if is_new or trip_idx >= len(new_trips):
        new_trips.append(Trip(route=[order.customer], orders=[order.oid], load_weight=order.weight, load_volume=order.volume))
        new_trip_opened = True
    else:
        t = new_trips[trip_idx]
        t.orders.append(order.oid)
        t.load_weight += order.weight
        t.load_volume += order.volume
        if order.customer not in t.route:
            insert_pos = 0 if pos is None else max(0, min(pos, len(t.route)))
            t.route.insert(insert_pos, order.customer)
        new_trip_opened = False

    new_cost = vehicle_sequence_cost(problem, vid, new_trips)

    # 固定启用成本：只有从未启用车辆第一次使用时才增加。
    fixed_delta = 0.0
    if not old_trips and new_trips:
        fixed_delta = vehicle.fixed_cost

    # 插入阶段的启发式趟次惩罚：只引导搜索，不改变最终评价函数。
    trip_bias = problem.trip_insert_penalty if new_trip_opened else 0.0

    # 迟到增量额外放大。注意 late_cost 已经进入 total，这里是搜索引导项。
    late_delta = max(0.0, new_cost["late_cost"] - old_cost["late_cost"])
    overtime_delta = max(0.0, new_cost["overtime_cost"] - old_cost["overtime_cost"])

    return (
        fixed_delta
        + (new_cost["total"] - old_cost["total"])
        + trip_bias
        + problem.late_insert_weight * late_delta
        + 2.0 * overtime_delta
    )


def route_delta_distance(problem: ProblemData, route: List[int], customer: int, pos: int) -> float:
    prev_node = 0 if pos == 0 else route[pos - 1]
    next_node = 0 if pos == len(route) else route[pos]
    return problem.distance(prev_node, customer) + problem.distance(customer, next_node) - problem.distance(prev_node, next_node)


def insertion_positions(problem: ProblemData, route: List[int], customer: int, max_positions: int, rng: random.Random) -> List[int]:
    if customer in route:
        return [-1]  # 表示无需插入新客户停靠点
    L = len(route)
    if L + 1 <= max_positions:
        return list(range(L + 1))
    # 首尾 + 与最近客户相邻的位置 + 少量随机位置
    dists = []
    for idx, c in enumerate(route):
        try:
            dists.append((problem.distance(c, customer), idx))
        except Exception:
            dists.append((1e9, idx))
    dists.sort()
    keep = {0, L}
    for _, idx in dists[:2]:
        keep.add(idx)
        keep.add(idx + 1)
    while len(keep) < max_positions:
        keep.add(rng.randint(0, L))
    return sorted(p for p in keep if 0 <= p <= L)


def approximate_move_score(problem: ProblemData, sol: Solution, vid: str, trip_idx: int, trip: Trip, order: Order, pos: Optional[int], is_new: bool) -> float:
    vehicle = problem.vehicles[vid]
    # 新车第一趟加入固定成本；活跃车新开趟不加固定成本。
    fixed_penalty = 0.0
    if vid not in sol.trips or not any(t.orders for t in sol.trips.get(vid, [])):
        fixed_penalty = vehicle.fixed_cost

    if is_new:
        dist_delta = problem.distance(0, order.customer) + problem.distance(order.customer, 0)
        tw_end = problem.time_windows[order.customer][1]
        # 简单估计：从 t0 出发是否接近最晚时间。
        arr = problem.t0_min + problem.travel_time_min(0, order.customer, problem.t0_min)
        late = max(0.0, arr - tw_end)
        return fixed_penalty + dist_delta * 5.0 + late * 1.5

    if order.customer in trip.route:
        dist_delta = 0.0
    else:
        assert pos is not None and pos >= 0
        dist_delta = route_delta_distance(problem, trip.route, order.customer, pos)

    # 容量越接近满载，略加惩罚，避免早期把所有小车塞爆。
    load_rate = (trip.load_weight + order.weight) / max(vehicle.cap_weight, 1e-9)
    vol_rate = (trip.load_volume + order.volume) / max(vehicle.cap_volume, 1e-9)
    cap_penalty = 10.0 * max(load_rate, vol_rate)

    # 时间窗粗略项：客户最晚时间越早越应优先；这里只影响位置选择不影响分配可行性。
    tw_end = problem.time_windows[order.customer][1]
    due_penalty = max(0.0, (problem.t0_min + dist_delta / max(ProblemData.speed_kmph(problem.t0_min), 1e-9) * 60) - tw_end) * 0.5

    return fixed_penalty + dist_delta * 5.0 + cap_penalty + due_penalty


def find_fast_insertion(
    problem: ProblemData,
    sol: Solution,
    oid: int,
    rng: random.Random,
    max_candidate_trips: int = 25,
    max_positions: int = 5,
) -> Optional[InsertionMove]:
    order = problem.orders[oid]
    moves: List[InsertionMove] = []

    # 1) 候选已有趟次：先粗筛容量，再按与 route 的空间相关性保留有限个。
    scored_trips: List[Tuple[float, str, int, Trip]] = []
    for vid, tidx, trip in sol.active_trips():
        vehicle = problem.vehicles[vid]
        if not capacity_ok(vehicle, trip, order):
            continue
        if order.customer in trip.route:
            score = -1e9
        elif trip.route:
            score = min(problem.distance(order.customer, c) for c in trip.route)
        else:
            score = problem.distance(0, order.customer)
        scored_trips.append((score, vid, tidx, trip))
    scored_trips.sort(key=lambda x: x[0])
    if len(scored_trips) > max_candidate_trips:
        scored_trips = scored_trips[:max_candidate_trips]

    for _, vid, tidx, trip in scored_trips:
        for pos in insertion_positions(problem, trip.route, order.customer, max_positions, rng):
            if pos == -1:
                score = insertion_delta_score(problem, sol, vid, tidx, order, None, False)
                moves.append(InsertionMove(vid, tidx, None, False, score))
            else:
                score = insertion_delta_score(problem, sol, vid, tidx, order, pos, False)
                moves.append(InsertionMove(vid, tidx, pos, False, score))

    # 2) 候选新趟次：活跃车辆可新开下一趟；每个未用车型给一个候选车。
    for vid in active_or_candidate_vehicle_ids(problem, sol):
        vehicle = problem.vehicles[vid]
        if order.weight > vehicle.cap_weight + 1e-9 or order.volume > vehicle.cap_volume + 1e-9:
            continue
        trips = sol.trips.get(vid, [])
        if len(trips) < problem.pmax:
            dummy = Trip(route=[], orders=[], load_weight=0.0, load_volume=0.0)
            score = insertion_delta_score(problem, sol, vid, len(trips), order, 0, True)
            moves.append(InsertionMove(vid, len(trips), 0, True, score))

    if not moves:
        return None
    moves.sort(key=lambda m: m.approx_score)
    return moves[0]


def apply_insertion(problem: ProblemData, sol: Solution, oid: int, move: InsertionMove) -> None:
    order = problem.orders[oid]
    if move.vehicle_id not in sol.trips:
        sol.trips[move.vehicle_id] = []
    trips = sol.trips[move.vehicle_id]
    if move.is_new_trip or move.trip_idx >= len(trips):
        trips.append(Trip(route=[order.customer], orders=[oid], load_weight=order.weight, load_volume=order.volume))
        return
    trip = trips[move.trip_idx]
    trip.orders.append(oid)
    trip.load_weight += order.weight
    trip.load_volume += order.volume
    if order.customer not in trip.route:
        pos = 0 if move.position is None else max(0, min(move.position, len(trip.route)))
        trip.route.insert(pos, order.customer)


def remove_order(problem: ProblemData, sol: Solution, oid: int) -> bool:
    order = problem.orders[oid]
    for vid, trips in list(sol.trips.items()):
        for trip in trips:
            if oid in trip.orders:
                trip.orders.remove(oid)
                trip.load_weight -= order.weight
                trip.load_volume -= order.volume
                still_customer = any(problem.orders[o].customer == order.customer for o in trip.orders)
                if not still_customer:
                    trip.route = [c for c in trip.route if c != order.customer]
                remove_empty_trips(sol)
                return True
    return False


def fast_repair(problem: ProblemData, sol: Solution, removed: List[int], rng: random.Random, order_rule: str,
                max_candidate_trips: int, max_positions: int) -> Tuple[Solution, bool]:
    new_sol = sol.copy()
    pool = list(removed)
    if order_rule == "random":
        rng.shuffle(pool)
    elif order_rule == "large_first":
        pool.sort(key=lambda oid: (problem.orders[oid].weight, problem.orders[oid].volume), reverse=True)
    else:
        pool.sort(key=lambda oid: problem.time_windows[problem.orders[oid].customer][1])

    for oid in pool:
        mv = find_fast_insertion(problem, new_sol, oid, rng, max_candidate_trips=max_candidate_trips, max_positions=max_positions)
        if mv is None:
            return new_sol, False
        apply_insertion(problem, new_sol, oid, mv)
    return new_sol, True


# ============================================================
# 5. 完整评价与输出明细
# ============================================================

def evaluate_solution(problem: ProblemData, sol: Solution, details: bool = False) -> Dict[str, Any]:
    fixed = energy = carbon_cost = carbon_kg = wait_cost = late_cost = overtime_cost = total_distance = 0.0
    vehicle_rows, trip_rows, arrival_rows, assign_rows = [], [], [], []
    assigned = set()

    for vid in sorted(sol.trips.keys()):
        trips = [t for t in sol.trips[vid] if t.orders]
        if not trips:
            continue
        vehicle = problem.vehicles[vid]
        fixed += vehicle.fixed_cost
        prev_ret = None
        for p_idx, trip in enumerate(trips, start=1):
            if trip.load_weight > vehicle.cap_weight + 1e-6 or trip.load_volume > vehicle.cap_volume + 1e-6:
                return {"total": 1e30, "feasible": False}

            dep = problem.t0_min if prev_ret is None else prev_ret + problem.reload_min
            route = list(trip.route)
            by_cust = trip_customer_orders(problem, trip)
            for c in by_cust:
                if c not in route:
                    route.append(c)

            load_w = trip.load_weight
            load_v = trip.load_volume
            cur = 0
            t = dep
            route_str = ["0"]
            trip_energy = trip_carbon_cost = trip_carbon_kg = trip_wait = trip_late = trip_distance = 0.0

            for cust in route:
                d = problem.distance(cur, cust)
                e_cost, c_cost, c_kg = problem.arc_energy_and_carbon(vehicle, cur, cust, t, load_w)
                travel = problem.travel_time_min(cur, cust, t)
                arr = t + travel
                a, b = problem.time_windows[cust]
                wait = max(0.0, a - arr)
                late = max(0.0, arr - b)
                start_service = arr + wait
                depart = start_service + problem.service_min

                energy += e_cost
                carbon_cost += c_cost
                carbon_kg += c_kg
                wait_cost += wait / 60.0 * problem.wait_cost_per_h
                late_cost += late / 60.0 * problem.late_cost_per_h
                total_distance += d
                trip_energy += e_cost
                trip_carbon_cost += c_cost
                trip_carbon_kg += c_kg
                trip_wait += wait / 60.0 * problem.wait_cost_per_h
                trip_late += late / 60.0 * problem.late_cost_per_h
                trip_distance += d

                delivered = by_cust.get(cust, [])
                dw = sum(problem.orders[oid].weight for oid in delivered)
                dv = sum(problem.orders[oid].volume for oid in delivered)

                if details:
                    arrival_rows.append({
                        "vehicle_id": vid,
                        "vehicle_type": vehicle.type_name,
                        "energy_type": vehicle.energy_type,
                        "trip_no": p_idx,
                        "customer_id": cust,
                        "arrival_min": arr,
                        "arrival_time": min_to_hhmm(arr),
                        "tw_start": min_to_hhmm(a),
                        "tw_end": min_to_hhmm(b),
                        "wait_min": wait,
                        "late_min": late,
                        "depart_time": min_to_hhmm(depart),
                        "delivered_weight": dw,
                        "delivered_volume": dv,
                        "orders_count": len(delivered),
                        "load_before_weight": load_w,
                        "load_before_volume": load_v,
                    })
                    for oid in delivered:
                        assign_rows.append({
                            "order_id": oid,
                            "customer_id": cust,
                            "vehicle_id": vid,
                            "vehicle_type": vehicle.type_name,
                            "trip_no": p_idx,
                            "weight": problem.orders[oid].weight,
                            "volume": problem.orders[oid].volume,
                        })

                load_w -= dw
                load_v -= dv
                cur = cust
                t = depart
                route_str.append(str(cust))
                assigned.update(delivered)

            d = problem.distance(cur, 0)
            e_cost, c_cost, c_kg = problem.arc_energy_and_carbon(vehicle, cur, 0, t, max(0.0, load_w))
            travel = problem.travel_time_min(cur, 0, t)
            ret = t + travel
            energy += e_cost
            carbon_cost += c_cost
            carbon_kg += c_kg
            total_distance += d
            trip_energy += e_cost
            trip_carbon_cost += c_cost
            trip_carbon_kg += c_kg
            trip_distance += d

            trip_overtime_cost = 0.0
            trip_overtime_min = 0.0
            if problem.max_return_min is not None and ret > problem.max_return_min:
                trip_overtime_min = ret - problem.max_return_min
                trip_overtime_cost = trip_overtime_min / 60.0 * problem.max_return_penalty_per_h
                overtime_cost += trip_overtime_cost

            route_str.append("0")

            if details:
                trip_rows.append({
                    "vehicle_id": vid,
                    "vehicle_type": vehicle.type_name,
                    "energy_type": vehicle.energy_type,
                    "trip_no": p_idx,
                    "depart_min": dep,
                    "depart_time": min_to_hhmm(dep),
                    "return_min": ret,
                    "return_time": min_to_hhmm(ret),
                    "route": " -> ".join(route_str),
                    "customers_count": len(route),
                    "orders_count": len(trip.orders),
                    "initial_weight": trip.load_weight,
                    "initial_volume": trip.load_volume,
                    "distance_km": trip_distance,
                    "energy_cost": trip_energy,
                    "carbon_cost": trip_carbon_cost,
                    "carbon_kg": trip_carbon_kg,
                    "wait_cost": trip_wait,
                    "late_cost": trip_late,
                    "overtime_min": trip_overtime_min,
                    "overtime_cost": trip_overtime_cost,
                })
            prev_ret = ret

        if details:
            vehicle_rows.append({
                "vehicle_id": vid,
                "vehicle_type": vehicle.type_name,
                "energy_type": vehicle.energy_type,
                "trips_used": len(trips),
            })

    unassigned = set(problem.orders) - assigned
    penalty = 1e8 * len(unassigned)
    total = fixed + energy + carbon_cost + wait_cost + late_cost + overtime_cost + penalty
    res = {
        "total": total,
        "fixed_cost": fixed,
        "energy_cost": energy,
        "carbon_cost": carbon_cost,
        "carbon_kg": carbon_kg,
        "wait_cost": wait_cost,
        "late_cost": late_cost,
        "overtime_cost": overtime_cost,
        "distance_km": total_distance,
        "unassigned_count": len(unassigned),
        "vehicles_used": len(sol.active_vehicle_ids()),
        "trips_used": len(sol.active_trips()),
        "feasible": len(unassigned) == 0 and total < 1e29,
    }
    if details:
        res.update({
            "vehicle_rows": vehicle_rows,
            "trip_rows": trip_rows,
            "arrival_rows": arrival_rows,
            "assignment_rows": assign_rows,
        })
    return res


# ============================================================
# 6. 摧毁算子
# ============================================================

def destroy_random(problem: ProblemData, sol: Solution, q: int, rng: random.Random) -> Tuple[Solution, List[int]]:
    ids = list(assigned_order_ids(sol))
    q = min(q, len(ids))
    removed = rng.sample(ids, q)
    new_sol = sol.copy()
    for oid in removed:
        remove_order(problem, new_sol, oid)
    return new_sol, removed


def destroy_trip(problem: ProblemData, sol: Solution, q: int, rng: random.Random) -> Tuple[Solution, List[int]]:
    trips = sol.active_trips()
    if not trips:
        return destroy_random(problem, sol, q, rng)
    # 倾向选择订单数较多的趟，这样移除更有结构性。
    weights = [max(1, len(t.orders)) for _, _, t in trips]
    vid, tidx, trip = rng.choices(trips, weights=weights, k=1)[0]
    removed = list(trip.orders)
    rng.shuffle(removed)
    removed = removed[:min(q, len(removed))]
    new_sol = sol.copy()
    for oid in removed:
        remove_order(problem, new_sol, oid)
    return new_sol, removed


def destroy_related(problem: ProblemData, sol: Solution, q: int, rng: random.Random) -> Tuple[Solution, List[int]]:
    ids = list(assigned_order_ids(sol))
    if not ids:
        return sol.copy(), []
    seed = rng.choice(ids)
    seed_c = problem.orders[seed].customer
    scored = []
    for oid in ids:
        c = problem.orders[oid].customer
        if c == seed_c:
            score = -1e9
        else:
            score = problem.distance(seed_c, c)
            # 时间窗越接近，相关性越强。
            score += 0.03 * abs(problem.time_windows[c][1] - problem.time_windows[seed_c][1])
        scored.append((score, oid))
    scored.sort(key=lambda x: x[0])
    removed = [oid for _, oid in scored[:min(q, len(scored))]]
    new_sol = sol.copy()
    for oid in removed:
        remove_order(problem, new_sol, oid)
    return new_sol, removed


# ============================================================
# 7. 初始解与 ALNS
# ============================================================

def construct_initial_solution(problem: ProblemData, rng: random.Random, max_candidate_trips: int, max_positions: int,
                               verbose: bool = True) -> Solution:
    order_ids = list(problem.orders.keys())
    # 客户时间窗越早优先，同客户订单按重量体积从大到小插入。
    order_ids.sort(key=lambda oid: (
        problem.time_windows[problem.orders[oid].customer][1],
        problem.orders[oid].customer,
        -problem.orders[oid].weight,
        -problem.orders[oid].volume,
    ))
    sol = Solution()
    t_start = time.time()
    for idx, oid in enumerate(order_ids, start=1):
        mv = find_fast_insertion(problem, sol, oid, rng, max_candidate_trips=max_candidate_trips, max_positions=max_positions)
        if mv is None:
            raise RuntimeError(f"初始解构造失败：订单 {oid} 无法插入。可尝试增大 Pmax 或检查容量。")
        apply_insertion(problem, sol, oid, mv)
        if verbose and (idx == 1 or idx % 300 == 0 or idx == len(order_ids)):
            elapsed = time.time() - t_start
            print(f"[初始化] 已插入 {idx:4d}/{len(order_ids)} 个订单，活跃车辆={len(sol.active_vehicle_ids())}, 趟次数={len(sol.active_trips())}, 用时={elapsed:.1f}s", flush=True)
    return sol


def alns_solve(
    problem: ProblemData,
    iterations: int,
    seed: int,
    min_remove: int,
    max_remove: int,
    log_every: int,
    verbose: bool,
    max_candidate_trips: int,
    max_positions: int,
    cooling: float = 0.995,
    segment: int = 50,
    reaction: float = 0.25,
) -> Tuple[Solution, Dict[str, Any]]:
    rng = random.Random(seed)
    start_time = time.time()

    if verbose:
        print("========== 快速版 ALNS 求解开始 ==========")
        print(f"[参数] iterations={iterations}, seed={seed}, pmax={problem.pmax}, min_remove={min_remove}, max_remove={max_remove}")
        print(f"[参数] max_candidate_trips={max_candidate_trips}, max_positions={max_positions}, log_every={log_every}")

    current = construct_initial_solution(problem, rng, max_candidate_trips, max_positions, verbose=verbose)
    current_eval = evaluate_solution(problem, current)
    best = current.copy()
    best_eval = dict(current_eval)

    if verbose:
        print(f"[初始化] 初始解评价完成: total={current_eval['total']:.2f}, vehicles={current_eval['vehicles_used']}, trips={current_eval['trips_used']}, distance={current_eval['distance_km']:.2f}km, carbon={current_eval['carbon_kg']:.2f}kg, late={current_eval['late_cost']:.2f}")

    destroy_ops = {
        "random": destroy_random,
        "related": destroy_related,
        "trip": destroy_trip,
    }
    repair_rules = ["earliest_due", "large_first", "random"]
    d_weights = {name: 1.0 for name in destroy_ops}
    r_weights = {name: 1.0 for name in repair_rules}
    d_scores = {name: 0.0 for name in destroy_ops}
    r_scores = {name: 0.0 for name in repair_rules}
    d_counts = {name: 0 for name in destroy_ops}
    r_counts = {name: 0 for name in repair_rules}

    temperature = max(1.0, 0.03 * current_eval["total"])
    history: List[Dict[str, Any]] = []
    n_orders = len(problem.orders)

    def choose(weights: Dict[str, float]) -> str:
        names = list(weights)
        vals = [max(1e-9, weights[n]) for n in names]
        return rng.choices(names, weights=vals, k=1)[0]

    for it in range(1, iterations + 1):
        dname = choose(d_weights)
        rname = choose(r_weights)
        upper_remove = min(max_remove, max(min_remove, int(0.06 * n_orders)))
        q = rng.randint(min_remove, upper_remove)

        partial, removed = destroy_ops[dname](problem, current, q, rng)
        candidate, ok = fast_repair(problem, partial, removed, rng, rname, max_candidate_trips, max_positions)
        cand_eval = evaluate_solution(problem, candidate) if ok else {"total": 1e30, "feasible": False}

        accepted = False
        score = 0.0
        if cand_eval["feasible"] and cand_eval["total"] < best_eval["total"]:
            best = candidate.copy()
            best_eval = dict(cand_eval)
            current = candidate
            current_eval = cand_eval
            accepted = True
            score = 8.0
        elif cand_eval["feasible"] and cand_eval["total"] < current_eval["total"]:
            current = candidate
            current_eval = cand_eval
            accepted = True
            score = 4.0
        elif cand_eval["feasible"]:
            delta = cand_eval["total"] - current_eval["total"]
            prob = math.exp(-max(0.0, delta) / max(1e-9, temperature))
            if rng.random() < prob:
                current = candidate
                current_eval = cand_eval
                accepted = True
                score = 1.0

        d_scores[dname] += score
        r_scores[rname] += score
        d_counts[dname] += 1
        r_counts[rname] += 1
        temperature *= cooling

        if it % segment == 0:
            for name in d_weights:
                if d_counts[name] > 0:
                    avg = d_scores[name] / d_counts[name]
                    d_weights[name] = (1 - reaction) * d_weights[name] + reaction * avg
                d_scores[name] = 0.0
                d_counts[name] = 0
            for name in r_weights:
                if r_counts[name] > 0:
                    avg = r_scores[name] / r_counts[name]
                    r_weights[name] = (1 - reaction) * r_weights[name] + reaction * avg
                r_scores[name] = 0.0
                r_counts[name] = 0

        should_log = it == 1 or it == iterations or score == 8.0 or (log_every > 0 and it % log_every == 0)
        if should_log:
            elapsed = time.time() - start_time
            eta = elapsed / max(1, it) * max(0, iterations - it)
            history.append({
                "iter": it,
                "current_total": current_eval["total"],
                "best_total": best_eval["total"],
                "temperature": temperature,
                "destroy": dname,
                "repair": rname,
                "accepted": accepted,
                "removed": len(removed),
                "vehicles_used": best_eval.get("vehicles_used"),
                "trips_used": best_eval.get("trips_used"),
                "distance_km": best_eval.get("distance_km"),
                "energy_cost": best_eval.get("energy_cost"),
                "carbon_cost": best_eval.get("carbon_cost"),
                "carbon_kg": best_eval.get("carbon_kg"),
                "wait_cost": best_eval.get("wait_cost"),
                "late_cost": best_eval.get("late_cost"),
                "overtime_cost": best_eval.get("overtime_cost"),
                "elapsed_sec": elapsed,
                "eta_sec": eta,
            })
            if verbose:
                flag = "*BEST*" if score == 8.0 else ""
                print(
                    f"[ALNS] iter={it:5d}/{iterations} {flag:6s} "
                    f"cur={current_eval['total']:12.2f} best={best_eval['total']:12.2f} "
                    f"veh={best_eval.get('vehicles_used', 0):3d} trips={best_eval.get('trips_used', 0):3d} "
                    f"dist={best_eval.get('distance_km', 0.0):9.2f}km "
                    f"late={best_eval.get('late_cost', 0.0):9.2f} "
                    f"ot={best_eval.get('overtime_cost', 0.0):8.2f} "
                    f"carbon={best_eval.get('carbon_kg', 0.0):9.2f}kg "
                    f"rm={len(removed):3d} d={dname:<8s} r={rname:<12s} "
                    f"acc={str(accepted):5s} T={temperature:10.2f} "
                    f"elapsed={elapsed/60:6.1f}min eta={eta/60:6.1f}min",
                    flush=True,
                )

    if verbose:
        elapsed = time.time() - start_time
        print("========== 快速版 ALNS 求解结束 ==========")
        print(f"[最优结果] total={best_eval['total']:.2f}, vehicles={best_eval.get('vehicles_used')}, trips={best_eval.get('trips_used')}, distance={best_eval.get('distance_km', 0.0):.2f}km, carbon={best_eval.get('carbon_kg', 0.0):.2f}kg, late={best_eval.get('late_cost', 0.0):.2f}, overtime={best_eval.get('overtime_cost', 0.0):.2f}, 用时={elapsed/60:.2f}min")
        print(f"[最终摧毁算子权重] {d_weights}")
        print(f"[最终修复算子权重] {r_weights}")

    return best, {"best_eval": best_eval, "history": history, "destroy_weights": d_weights, "repair_weights": r_weights}


# ============================================================
# 8. 输出
# ============================================================

def solution_to_jsonable(sol: Solution) -> Dict[str, Any]:
    data = {}
    for vid, trips in sol.trips.items():
        arr = []
        for t in trips:
            if t.orders:
                arr.append({"route": t.route, "orders": t.orders, "load_weight": t.load_weight, "load_volume": t.load_volume})
        if arr:
            data[vid] = arr
    return data


def save_outputs(problem: ProblemData, sol: Solution, meta: Dict[str, Any], output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    ev = evaluate_solution(problem, sol, details=True)

    cost_df = pd.DataFrame([{
        "total_cost": ev["total"],
        "fixed_cost": ev["fixed_cost"],
        "energy_cost": ev["energy_cost"],
        "carbon_cost": ev["carbon_cost"],
        "carbon_kg": ev["carbon_kg"],
        "wait_cost": ev["wait_cost"],
        "late_cost": ev["late_cost"],
        "overtime_cost": ev["overtime_cost"],
        "distance_km": ev["distance_km"],
        "vehicles_used": ev["vehicles_used"],
        "trips_used": ev["trips_used"],
        "unassigned_count": ev["unassigned_count"],
    }])
    vehicle_df = pd.DataFrame(ev["vehicle_rows"])
    trip_df = pd.DataFrame(ev["trip_rows"])
    arrival_df = pd.DataFrame(ev["arrival_rows"])
    assignment_df = pd.DataFrame(ev["assignment_rows"])
    history_df = pd.DataFrame(meta.get("history", []))

    cost_df.to_csv(os.path.join(output_dir, "cost_breakdown.csv"), index=False, encoding="utf-8-sig")
    vehicle_df.to_csv(os.path.join(output_dir, "vehicle_plan.csv"), index=False, encoding="utf-8-sig")
    trip_df.to_csv(os.path.join(output_dir, "trip_routes.csv"), index=False, encoding="utf-8-sig")
    arrival_df.to_csv(os.path.join(output_dir, "customer_arrivals.csv"), index=False, encoding="utf-8-sig")
    assignment_df.to_csv(os.path.join(output_dir, "order_assignment.csv"), index=False, encoding="utf-8-sig")
    history_df.to_csv(os.path.join(output_dir, "alns_history.csv"), index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(os.path.join(output_dir, "solution_summary.xlsx"), engine="openpyxl") as writer:
        cost_df.to_excel(writer, sheet_name="cost_breakdown", index=False)
        vehicle_df.to_excel(writer, sheet_name="vehicle_plan", index=False)
        trip_df.to_excel(writer, sheet_name="trip_routes", index=False)
        arrival_df.to_excel(writer, sheet_name="customer_arrivals", index=False)
        assignment_df.to_excel(writer, sheet_name="order_assignment", index=False)
        history_df.to_excel(writer, sheet_name="alns_history", index=False)

    with open(os.path.join(output_dir, "best_solution.json"), "w", encoding="utf-8") as f:
        json.dump(solution_to_jsonable(sol), f, ensure_ascii=False, indent=2)

    print("\n========== 最优方案成本构成 ==========")
    print(cost_df.to_string(index=False))
    print(f"\n结果已输出到：{output_dir}")
    print("主要文件：")
    print("  - solution_summary.xlsx：总结果表")
    print("  - trip_routes.csv：车辆趟次路径")
    print("  - customer_arrivals.csv：客户到达时间")
    print("  - order_assignment.csv：订单分配")
    print("  - cost_breakdown.csv：成本构成")


# ============================================================
# 9. 主程序
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="快速版 ALNS 求解城市绿色物流配送调度问题一")
    parser.add_argument("--orders", required=True, help="订单信息.xlsx 路径")
    parser.add_argument("--distance", required=True, help="距离矩阵.xlsx 路径")
    parser.add_argument("--time_windows", required=True, help="时间窗.xlsx 路径")
    parser.add_argument("--output", default="results_q1_fast", help="输出目录")
    parser.add_argument("--iterations", type=int, default=300, help="ALNS 迭代次数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--pmax", type=int, default=2, help="单车最大趟次数") # =========================================================
    parser.add_argument("--t0", default="08:00", help="规划期开始时刻，例如 08:00")
    parser.add_argument("--service_min", type=float, default=20.0, help="客户服务时间，分钟")
    parser.add_argument("--reload_min", type=float, default=20.0, help="车辆回仓后重新装载准备时间，分钟")
    parser.add_argument("--max_return", default="22:00", help="车辆每趟最晚回仓时间；设为 none 可关闭该软约束")
    parser.add_argument("--max_return_penalty_per_h", type=float, default=5000.0, help="超过最晚回仓时间的惩罚成本，元/小时")
    parser.add_argument("--trip_insert_penalty", type=float, default=150.0, help="插入阶段新开趟次的启发式惩罚，只影响搜索不进入最终成本")
    parser.add_argument("--late_insert_weight", type=float, default=8.0, help="插入阶段迟到增量放大系数，用于抑制严重迟到")
    parser.add_argument("--distance_unit", choices=["auto", "km", "m"], default="auto", help="距离矩阵单位；auto 会根据数值规模自动判断")
    parser.add_argument("--min_remove", type=int, default=8, help="每轮最少移除订单数")
    parser.add_argument("--max_remove", type=int, default=35, help="每轮最多移除订单数；越大越慢")
    parser.add_argument("--candidate_trips", type=int, default=20, help="每个订单插入时最多考察的已有趟次数；越大越慢")
    parser.add_argument("--candidate_positions", type=int, default=4, help="每个候选趟次最多考察的插入位置数；越大越慢")
    parser.add_argument("--log_every", type=int, default=20, help="每隔多少轮输出一次进度；0 表示只输出首尾")
    parser.add_argument("--quiet", action="store_true", help="关闭大部分控制台输出")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.quiet:
        print("[读取] 正在读取输入文件...", flush=True)
        print(f"[读取] 订单文件: {args.orders}", flush=True)
        print(f"[读取] 距离矩阵: {args.distance}", flush=True)
        print(f"[读取] 时间窗文件: {args.time_windows}", flush=True)

    problem = load_problem(args)

    if not args.quiet:
        print("[读取] 输入文件读取完成。", flush=True)
        print(f"[数据] 订单数: {len(problem.orders)}", flush=True)
        print(f"[数据] 客户数: {len(problem.customer_orders)}", flush=True)
        print(f"[数据] 车辆数: {len(problem.vehicles)}", flush=True)
        print(f"[数据] Pmax: {problem.pmax}, 开始时间: {min_to_hhmm(problem.t0_min)}", flush=True)
        print(f"[数据] 服务时间: {problem.service_min:.1f}min, 回仓装载准备: {problem.reload_min:.1f}min", flush=True)
        mr = "关闭" if problem.max_return_min is None else min_to_hhmm(problem.max_return_min)
        print(f"[数据] 最晚回仓软约束: {mr}, 超时惩罚={problem.max_return_penalty_per_h:.1f}元/h", flush=True)
        print(f"[数据] 插入引导: trip_insert_penalty={problem.trip_insert_penalty:.1f}, late_insert_weight={problem.late_insert_weight:.1f}", flush=True)

    best, meta = alns_solve(
        problem,
        iterations=args.iterations,
        seed=args.seed,
        min_remove=args.min_remove,
        max_remove=args.max_remove,
        log_every=args.log_every,
        verbose=not args.quiet,
        max_candidate_trips=args.candidate_trips,
        max_positions=args.candidate_positions,
    )
    save_outputs(problem, best, meta, args.output)


if __name__ == "__main__":
    main()
