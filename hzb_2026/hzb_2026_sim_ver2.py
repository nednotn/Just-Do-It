import numpy as np
import pandas as pd
import random
import copy

# =================================================================
# 1. 基础配置
# =================================================================
VEHICLE_TYPES = [
    (3000, 15.0, 400, False, 10, 'EV1'),
    (1250, 8.5, 400, False, 15, 'EV2'),
    (3000, 13.5, 400, True, 60, 'F1'),
    (1500, 10.8, 400, True, 50, 'F2'),
    (1250, 6.5, 400, True, 50, 'F3'),
]

def generate_mock_data(num_cust=100, target_orders=2000):
    cust_ids = list(range(1, num_cust + 1))
    # 模拟更紧凑的时间窗
    time_windows = {i: (np.random.uniform(9.0, 15.0), np.random.uniform(16.0, 21.0)) for i in cust_ids}
    orders = []
    for o_idx in range(1, target_orders + 1):
        c_id = random.choice(cust_ids)
        w = np.random.uniform(10, 80) 
        v = 0.0022 * w + 0.01 + np.random.uniform(0, 0.01)
        orders.append({'o_id': o_idx, 'c_id': c_id, 'weight': w, 'volume': v})
    return orders, time_windows

ORDER_POOL, CUST_TIME_WINDOWS = generate_mock_data(100, 2000)

# =================================================================
# 2. 仿真引擎（包含时间窗惩罚计算）
# =================================================================

def get_dist(i, j):
    np.random.seed(int(i * 100 + j))
    return np.random.uniform(5, 20)

def simulate_trip(orders, v_type_info, ready_time):
    max_w, max_v, s_fee, is_fuel, _, _ = v_type_info
    stops = sorted(list(set(o['c_id'] for o in orders)), key=lambda x: CUST_TIME_WINDOWS[x][0])
    
    # --- 优化：智能推算出发时间 ---
    # 计算到第一个点所需的行驶时间
    travel_to_first = get_dist(0, stops[0]) / 35.0
    # 理想出发时间 = 第一个点开门时间 - 行驶时间
    ideal_dep = CUST_TIME_WINDOWS[stops[0]][0] - travel_to_first
    # 实际出发 = max(车辆就绪时间, 理想出发时间, 公司开门8:00)
    actual_dep = max(ready_time, ideal_dep, 8.0)
    
    curr_t, curr_loc = actual_dep, 0
    wait_cost, delay_cost, energy_cost = 0, 0, 0
    w_sum = 0
    
    for c_id in stops:
        dist = get_dist(curr_loc, c_id)
        curr_t += (dist / 35.0)
        
        e, l = CUST_TIME_WINDOWS[c_id]
        if curr_t < e:
            # 早到惩罚 (20元/小时)
            wait_cost += (e - curr_t) * 20
            curr_t = e # 等到开门
        elif curr_t > l:
            # 晚到惩罚 (50元/小时)
            delay_cost += (curr_t - l) * 50
            
        this_w = sum(o['weight'] for o in orders if o['c_id'] == c_id)
        price = 9.27 if is_fuel else 1.97
        energy_cost += (dist * 0.4) * (1 + 0.5 * (w_sum/max_w)) * price
        
        w_sum += this_w
        curr_t += 20/60 # 服务时间
        curr_loc = c_id

    dist_back = get_dist(curr_loc, 0)
    back_t = curr_t + (dist_back / 35.0)
    total_trip_cost = s_fee + wait_cost + delay_cost + energy_cost + (dist_back * 1.5)
    
    return {
        'cost': total_trip_cost,
        'wait_penalty': wait_cost,
        'delay_penalty': delay_cost,
        'end_t': back_t + 0.5,
        'start_t': actual_dep,
        'w_rate': w_sum / max_w
    }

# =================================================================
# 3. 调度管理
# =================================================================

def run_optimized_simulation():
    all_orders = copy.deepcopy(ORDER_POOL)
    all_orders.sort(key=lambda x: CUST_TIME_WINDOWS[x['c_id']][0])
    
    # 初始化车辆
    fleet = []
    for t in VEHICLE_TYPES:
        for i in range(t[4]):
            fleet.append({'id': f"{t[5]}_{i+1:02d}", 'info': t, 'ready': 8.0, 'history': []})

    o_ptr = 0
    while o_ptr < len(all_orders):
        fleet.sort(key=lambda x: x['ready'])
        v = fleet[0]
        v_info = v['info']
        
        # 贪婪装载
        trip_orders, tw, tv = [], 0, 0
        temp_ptr = o_ptr
        while temp_ptr < len(all_orders):
            o = all_orders[temp_ptr]
            if (tw + o['weight'] <= v_info[0]) and (tv + o['volume'] <= v_info[1]):
                trip_orders.append(o); tw += o['weight']; tv += o['volume']; temp_ptr += 1
            else: break
        
        res = simulate_trip(trip_orders, v_info, v['ready'])
        
        if res['end_t'] <= 23.5:
            v['history'].append(res)
            v['ready'] = res['end_t']
            o_ptr = temp_ptr
        else:
            # 如果这辆车没法在下班前送完这批，尝试下一辆更早的车或放弃
            v['ready'] = 24.0 # 标记该车今日报废

    # =================================================================
    # 4. 结果报表
    # =================================================================
    print(f"\n{'车辆ID':<10} | {'总航次':<4} | {'出发':<5} | {'返回':<5} | {'早到惩罚':<7} | {'超时惩罚':<7} | {'装载率'}")
    print("-" * 85)
    
    total_wait, total_delay, total_cost = 0, 0, 0
    for v in sorted(fleet, key=lambda x: x['id']):
        if not v['history']: continue
        
        # 统计该车全天数据
        v_wait = sum(h['wait_penalty'] for h in v['history'])
        v_delay = sum(h['delay_penalty'] for h in v['history'])
        v_cost = sum(h['cost'] for h in v['history'])
        v_load = np.mean([h['w_rate'] for h in v['history']])
        
        total_wait += v_wait
        total_delay += v_delay
        total_cost += v_cost
        
        # 打印第一趟的时间范围作为代表
        h1 = v['history'][0]
        hn = v['history'][-1]
        print(f"{v['id']:<10} | {len(v['history']):<6} | {int(h1['start_t']):02d}:{int(h1['start_t']%1*60):02d} | {int(hn['end_t']):02d}:{int(hn['end_t']%1*60):02d} | {v_wait:>8.1f} | {v_delay:>8.1f} | {v_load:>6.1%}")

    print("-" * 85)
    print(f"系统汇总指标:")
    print(f"1. 累计等待成本 (Wait Cost):  {total_wait:.2f} 元")
    print(f"2. 累计超时惩罚 (Delay Cost): {total_delay:.2f} 元")
    print(f"3. 包含罚金的总运营成本:       {total_cost:.2f} 元")

if __name__ == "__main__":
    run_optimized_simulation()