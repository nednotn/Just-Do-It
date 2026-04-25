import numpy as np
import pandas as pd
import random
import copy

# =================================================================
# 1. 基础配置与确定性基准生成
# =================================================================
VEHICLE_TYPES = [
    (3000, 15.0, 400, False, 10, 'EV1'),
    (1250, 8.5, 400, False, 15, 'EV2'),
    (3000, 13.5, 400, True, 60, 'F1'),
    (1500, 10.8, 400, True, 50, 'F2'),
    (1250, 6.5, 400, True, 50, 'F3'),
]

def generate_fixed_base_data(num_cust=100, target_orders=2500):
    """固定种子，生成窄时间窗（1.5h）和确定性订单"""
    random.seed(42)
    np.random.seed(42)
    
    cust_ids = list(range(1, num_cust + 1))
    
    # 客户坐标固定 (用于距离计算)
    cust_coords = {i: np.random.uniform(0, 50, size=2) for i in cust_ids}
    cust_coords[0] = np.array([25, 25]) # 仓库坐标
    
    # 1.5小时窄时间窗 (8:30 - 20:30)
    time_windows = {}
    for i in cust_ids:
        start_t = np.random.uniform(8.5, 19.0)
        time_windows[i] = [start_t, start_t + 1.5]
    
    orders = []
    for o_idx in range(1, target_orders + 1):
        c_id = random.choice(cust_ids)
        # 混合泊松分布 (均值150, 4%离群大单上限2500)
        w = min(np.random.poisson(2000), 2500) if random.random() < 0.04 else max(10, np.random.poisson(150))
        v = 0.0022 * w + 0.01 + np.random.uniform(0, 0.01)
        orders.append({'o_id': o_idx, 'c_id': c_id, 'weight': w, 'volume': min(v, 15.0)})
        
    return orders, time_windows, cust_coords

# =================================================================
# 2. 距离与计算引擎
# =================================================================
def get_dist(c1, c2, coords):
    return np.linalg.norm(coords[c1] - coords[c2])

def simulate_trip(orders, v_type_info, ready_time, tw_data, coords):
    if not orders: return None
    max_w, max_v, s_fee, is_fuel, _, _ = v_type_info
    
    # 路径：按时间窗开启顺序
    stops = sorted(list(set(o['c_id'] for o in orders)), key=lambda x: tw_data[x][0])
    
    travel_to_first = get_dist(0, stops[0], coords) / 35.0
    actual_dep = max(ready_time, tw_data[stops[0]][0] - travel_to_first, 8.5)
    
    curr_t, curr_loc, trip_delay, energy_cost, w_sum = actual_dep, 0, 0, 0, 0
    
    for c_id in stops:
        dist = get_dist(curr_loc, c_id, coords)
        curr_t += (dist / 35.0)
        e, l = tw_data[c_id]
        
        if curr_t < e:
            curr_t = e 
        elif curr_t > l:
            trip_delay += (curr_t - l) # 记录延误小时数
            
        this_w = sum(o['weight'] for o in orders if o['c_id'] == c_id)
        price = 9.27 if is_fuel else 1.97
        energy_cost += (dist * 0.4) * (1 + 0.5 * (w_sum/max_w)) * price
        w_sum += this_w
        curr_t += 0.4 # 卸货服务
        curr_loc = c_id

    back_t = curr_t + (get_dist(curr_loc, 0, coords) / 35.0)
    cost = s_fee + energy_cost + (trip_delay * 150) + (get_dist(curr_loc, 0, coords) * 1.5)
    
    return {'cost': cost, 'end_t': back_t + 0.3, 'w_rate': w_sum / max_w, 'delay': trip_delay}

# =================================================================
# 3. 动态调度主程序
# =================================================================
def run_final_simulation():
    # 数据准备
    BASE_ORDERS, TIME_WINDOWS, COORDS = generate_fixed_base_data()
    pending_orders = copy.deepcopy(BASE_ORDERS)
    current_tw = copy.deepcopy(TIME_WINDOWS)
    
    stats = {'cancel': 0, 'new': 0, 'total_delay': 0.0}
    fleet = []
    for t in VEHICLE_TYPES:
        for i in range(t[4]):
            fleet.append({'id': f"{t[5]}_{i+1:02d}", 'info': t, 'ready': 8.5, 'history': []})

    print(f">>> 启动研究级仿真 | 时间窗: 1.5h | 总订单(基准): {len(pending_orders)} <<<")
    
    sim_clock = 8.5
    while (pending_orders or any(v['ready'] < 22.0 for v in fleet)) and sim_clock < 24.0:
        # 4. 随机扰动 (此处不固定种子，用于测试鲁棒性)
        if random.random() < 0.05 and pending_orders:
            pending_orders.pop(random.randrange(len(pending_orders)))
            stats['cancel'] += 1
        if random.random() < 0.05:
            w = min(np.random.poisson(150), 2500)
            pending_orders.append({'o_id': 7777, 'c_id': random.randint(1, 100), 'weight': w, 'volume': 0.0022*w})
            stats['new'] += 1

        # 调度逻辑
        pending_orders.sort(key=lambda x: current_tw[x['c_id']][0])
        idle_vehicles = [v for v in fleet if v['ready'] <= sim_clock]
        idle_vehicles.sort(key=lambda x: x['info'][0], reverse=True)

        for v in idle_vehicles:
            if not pending_orders: break
            max_w, max_v = v['info'][0], v['info'][1]
            trip_indices, curr_w, curr_v = [], 0, 0
            
            for i in range(len(pending_orders)):
                o = pending_orders[i]
                if curr_w + o['weight'] <= max_w and curr_v + o['volume'] <= max_v:
                    trip_indices.append(i)
                    curr_w += o['weight']; curr_v += o['volume']
            
            if trip_indices:
                trip_orders = [pending_orders[i] for i in trip_indices]
                res = simulate_trip(trip_orders, v['info'], v['ready'], current_tw, COORDS)
                v['history'].append(res)
                v['ready'] = res['end_t']
                stats['total_delay'] += res['delay']
                for i in sorted(trip_indices, reverse=True): pending_orders.pop(i)

        sim_clock += 0.5 

    # =================================================================
    # 5. 详细报表：车辆使用情况
    # =================================================================
    print("\n" + "="*105)
    print(f"{'车辆ID':<10} | {'航次':<4} | {'最后回仓':<6} | {'平均装载':<6} | {'累计延误(h)':<10} | {'累计成本':<10}")
    print("-" * 105)
    
    active_count, total_cost = 0, 0
    for v in sorted(fleet, key=lambda x: x['id']):
        if not v['history']: continue
        
        active_count += 1
        v_delay = sum(h['delay'] for h in v['history'])
        v_cost = sum(h['cost'] for h in v['history'])
        v_load = np.mean([h['w_rate'] for h in v['history']])
        total_cost += v_cost
        last_t = v['history'][-1]['end_t']
        
        t_str = f"{int(last_t):02d}:{int((last_t%1)*60):02d}"
        print(f"{v['id']:<10} | {len(v['history']):<4} | {t_str:<8} | {v_load:>8.1%} | {v_delay:>12.2f} | {v_cost:>10.1f}")

    print("-" * 105)
    print(f"【最终鲁棒性汇总】")
    print(f" • 动用车辆: {active_count}/{len(fleet)} | 剩余积压: {len(pending_orders)}")
    print(f" • 异常统计: 取消 {stats['cancel']} 单 | 新增 {stats['new']} 单")
    print(f" • 核心指标 - 总延误时长: {stats['total_delay']:.2f} 小时")
    print(f" • 核心指标 - 总运营成本: {total_cost:.2f} 元")
    print("="*105)

if __name__ == "__main__":
    run_final_simulation()