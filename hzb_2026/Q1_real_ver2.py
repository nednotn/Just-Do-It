import numpy as np
import pandas as pd
import copy

# =================================================================
# 1. 配置与工具函数
# =================================================================
VEHICLE_TYPES = [
    (3000, 15.0, 400, False, 10, 'EV1'),
    (1250, 8.5, 400, False, 15, 'EV2'),
    (3000, 13.5, 400, True, 60, 'F1'),
    (1500, 10.8, 400, True, 50, 'F2'),
    (1250, 6.5, 400, True, 50, 'F3'),
]

AVG_SPEED = 35.0 
SERVICE_TIME = 20/60 

def time_to_float(time_val):
    if isinstance(time_val, (int, float)): return float(time_val)
    time_str = str(time_val).strip()
    try:
        if ':' in time_str:
            h, m = time_str.split(':')
            return int(h) + int(m) / 60.0
        return float(time_str)
    except: return 8.0 

# =================================================================
# 2. 数据加载
# =================================================================
def load_all_resources(order_file, window_file, dist_file):
    try:
        df_orders = pd.read_excel(order_file)
        df_orders.columns = [c.strip() for c in df_orders.columns]
        orders = [{
            'o_id': r['订单编号'], 'c_id': int(r['目标客户编号']),
            'weight': float(r['重量']), 'volume': float(r['体积'])
        } for _, r in df_orders.iterrows() if r['目标客户编号'] > 0]

        df_windows = pd.read_excel(window_file)
        df_windows.columns = [c.strip() for c in df_windows.columns]
        time_windows = {int(r['客户编号']): (time_to_float(r['开始时间']), time_to_float(r['结束时间'])) 
                        for _, r in df_windows.iterrows()}
        
        dist_df = pd.read_excel(dist_file, index_col=0)
        dist_matrix = dist_df.values
        return orders, time_windows, dist_matrix
    except Exception as e:
        print(f"数据加载失败: {e}")
        return [], {}, None

ORDER_POOL, CUST_TIME_WINDOWS, DIST_MATRIX = load_all_resources('订单信息.xlsx', '时间窗.xlsx', '距离矩阵.xlsx')

def get_dist(i, j):
    try: return float(DIST_MATRIX[int(i)][int(j)])
    except: return 10.0

# =================================================================
# 3. 增强仿真引擎（新增超时时长统计）
# =================================================================
def simulate_trip(orders, v_type_info, ready_time):
    if not orders: return None
    max_w, max_v, s_fee, is_fuel, _, _ = v_type_info
    
    # 路径：按截止时间排序
    raw_stops = []
    seen = set()
    for o in orders:
        if o['c_id'] not in seen:
            raw_stops.append(o['c_id'])
            seen.add(o['c_id'])
    stops = sorted(raw_stops, key=lambda x: CUST_TIME_WINDOWS.get(x, (8,20))[1])
    
    travel_to_first = get_dist(0, stops[0]) / AVG_SPEED
    actual_dep = max(ready_time, CUST_TIME_WINDOWS.get(stops[0], (8,20))[0] - travel_to_first, 8.0)
    
    curr_t, curr_loc, w_sum = actual_dep, 0, 0
    wait_cost, delay_cost, energy_cost = 0, 0, 0
    total_delay_hours = 0.0  # 新增：记录总超时小时数
    
    for c_id in stops:
        dist = get_dist(curr_loc, c_id)
        curr_t += (dist / AVG_SPEED)
        e, l = CUST_TIME_WINDOWS.get(c_id, (8,20))
        
        if curr_t < e:
            wait_cost += (e - curr_t) * 20
            curr_t = e
        elif curr_t > l:
            delay_duration = curr_t - l
            total_delay_hours += delay_duration # 累计超时时长
            delay_cost += delay_duration * 50
        
        energy_cost += (dist * 0.4) * (1 + 0.5 * (w_sum/max_w)) * (9.27 if is_fuel else 1.97)
        w_sum += sum(o['weight'] for o in orders if o['c_id'] == c_id)
        curr_t += SERVICE_TIME
        curr_loc = c_id

    dist_back = get_dist(curr_loc, 0)
    back_t = curr_t + (dist_back / AVG_SPEED)
    total_cost = s_fee + wait_cost + delay_cost + energy_cost + (dist_back * 1.5)
    
    return {
        'cost': total_cost, 
        'end_t': back_t, 
        'start_t': actual_dep, 
        'delay_hours': total_delay_hours, # 返回超时时长
        'path': stops
    }

# =================================================================
# 4. 优化调度逻辑
# =================================================================
def run_optimized_simulation():
    if not ORDER_POOL: return
    
    # EDF 排序：截止时间越早越优先
    all_orders = sorted(copy.deepcopy(ORDER_POOL), key=lambda x: CUST_TIME_WINDOWS.get(x['c_id'], (8,20))[1])
    
    fleet = []
    for t in VEHICLE_TYPES:
        for i in range(t[4]):
            fleet.append({'id': f"{t[5]}_{i+1:02d}", 'info': t, 'ready': 8.0, 'history': []})

    o_ptr, total_cnt = 0, len(all_orders)
    undelivered = []

    while o_ptr < total_cnt:
        # 优化车辆选择策略：优先选择已使用的、且能最早回场的车，以提高复用
        # 排序权重：ready时间 + (0 if 已使用 else 100) -> 倾向于压榨已出动的车
        fleet.sort(key=lambda x: (x['ready'], 0 if x['history'] else 1))
        v = fleet[0]
        
        if v['ready'] >= 22.0:
            undelivered = all_orders[o_ptr:]
            break

        trip_orders, tw, tv, temp_ptr = [], 0, 0, o_ptr
        
        # 尝试装载
        while temp_ptr < total_cnt:
            o = all_orders[temp_ptr]
            if (tw + o['weight'] <= v['info'][0]) and (tv + o['volume'] <= v['info'][1]):
                # 预校验路径可行性
                res_test = simulate_trip(trip_orders + [o], v['info'], v['ready'])
                if res_test['end_t'] <= 23.9:
                    trip_orders.append(o)
                    tw += o['weight']; tv += o['volume']
                    temp_ptr += 1
                else: break
            else: break
        
        if not trip_orders:
            o_ptr += 1
            continue

        # 执行正式模拟并记录
        res = simulate_trip(trip_orders, v['info'], v['ready'])
        v['history'].append(res)
        v['ready'] = res['end_t']
        o_ptr = temp_ptr

    # =================================================================
    # 5. 报表展示
    # =================================================================
    total_cost = 0
    total_delay = 0
    used_vehicles = 0
    reused_count = 0

    print(f"{'车辆ID':<10} | {'航次数':<6} | {'最后回场':<8} | {'该车总超时(h)':<10}")
    print("-" * 50)
    for v in fleet:
        if v['history']:
            used_vehicles += 1
            v_delay = sum(h['delay_hours'] for h in v['history'])
            v_cost = sum(h['cost'] for h in v['history'])
            total_delay += v_delay
            total_cost += v_cost
            if len(v['history']) > 1: reused_count += 1
            print(f"{v['id']:<10} | {len(v['history']):<7} | {v['ready']:>8.2f} | {v_delay:>10.2f}")

    print("\n" + "="*20 + " 总体统计结果 " + "="*20)
    print(f"1. 配送进度: {total_cnt - len(undelivered)} / {total_cnt}")
    print(f"2. 使用车辆总数: {used_vehicles} 台")
    print(f"3. 发生复用的车辆: {reused_count} 台")
    print(f"4. 总计运营成本: {total_cost:.2f} 元")
    print(f"5. 全局总超时时间: {total_delay:.2f} 小时")
    print("=" * 55)

if __name__ == "__main__":
    run_optimized_simulation()