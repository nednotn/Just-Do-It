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

try:
    ORDER_POOL, CUST_TIME_WINDOWS, DIST_MATRIX = load_all_resources('订单信息.xlsx', '时间窗.xlsx', '距离矩阵.xlsx')
except Exception as e:
    print(f"数据加载失败: {e}"); exit()

def get_dist(i, j):
    try: return float(DIST_MATRIX[int(i)][int(j)])
    except: return 10.0

# =================================================================
# 3. 仿真引擎
# =================================================================
def simulate_trip(orders, v_type_info, ready_time):
    if not orders: return None
    max_w, max_v, s_fee, is_fuel, _, _ = v_type_info
    
    # 路径规划：按时间窗起始时间排序
    raw_stops = list(dict.fromkeys([o['c_id'] for o in orders]))
    stops = sorted(raw_stops, key=lambda x: CUST_TIME_WINDOWS.get(x, (8,20))[0])
    
    travel_to_first = get_dist(0, stops[0]) / 35.0
    # 出发时间：要么是车辆就绪时间，要么是第一个客户开启时间减去行驶时间
    actual_dep = max(ready_time, CUST_TIME_WINDOWS.get(stops[0], (8,20))[0] - travel_to_first, 8.0)
    
    curr_t, curr_loc, w_sum, wait_cost, delay_cost, energy_cost = actual_dep, 0, 0, 0, 0, 0
    
    for c_id in stops:
        dist = get_dist(curr_loc, c_id)
        curr_t += (dist / 35.0)
        e, l = CUST_TIME_WINDOWS.get(c_id, (8,20))
        if curr_t < e:
            wait_cost += (e - curr_t) * 20
            curr_t = e
        elif curr_t > l:
            delay_cost += (curr_t - l) * 50
        
        energy_cost += (dist * 0.4) * (1 + 0.5 * (w_sum/max_w)) * (9.27 if is_fuel else 1.97)
        w_sum += sum(o['weight'] for o in orders if o['c_id'] == c_id)
        curr_t += 20/60
        curr_loc = c_id

    dist_back = get_dist(curr_loc, 0)
    back_t = curr_t + (dist_back / 35.0)
    total_cost = s_fee + wait_cost + delay_cost + energy_cost + (dist_back * 1.5)
    
    return {
        'cost': total_cost, 'end_t': back_t + 0.5, 'start_t': actual_dep, 
        'w_rate': w_sum / max_w, 'path': stops
    }

# =================================================================
# 4. 执行调度（支持一车多往返）
# =================================================================
def run_optimized_simulation():
    all_orders = sorted(copy.deepcopy(ORDER_POOL), key=lambda x: CUST_TIME_WINDOWS.get(x['c_id'], (8,20))[0])
    fleet = []
    for t in VEHICLE_TYPES:
        for i in range(t[4]):
            fleet.append({'id': f"{t[5]}_{i+1:02d}", 'info': t, 'ready': 8.0, 'history': []})

    o_ptr, total_cnt = 0, len(all_orders)

    while o_ptr < total_cnt:
        # 1. 筛选当前还没“跑死”的车辆，并按就绪时间升序排列
        available = [v for v in fleet if v['ready'] < 21.0] 
        if not available:
            print(f"\n[警告] 所有车辆均已饱和，剩余 {total_cnt - o_ptr} 个订单无法配送。")
            break

        available.sort(key=lambda x: x['ready'])
        v = available[0] # 总是挑最先回来的那台车

        # 2. 尝试装货
        trip_orders, tw, tv, temp_ptr = [], 0, 0, o_ptr
        while temp_ptr < total_cnt:
            o = all_orders[temp_ptr]
            if (tw + o['weight'] <= v['info'][0]) and (tv + o['volume'] <= v['info'][1]):
                trip_orders.append(o); tw += o['weight']; tv += o['volume']; temp_ptr += 1
            else: break
        
        if not trip_orders:
            print(f"订单 {all_orders[o_ptr]['o_id']} 太大，所有车型均无法承载。"); o_ptr += 1; continue

        # 3. 仿真计算
        res = simulate_trip(trip_orders, v['info'], v['ready'])
        
        if res['end_t'] <= 23.8:
            # 记录这次航次
            trip_idx = len(v['history']) + 1
            print(f"[调度成功] 车辆: {v['id']} | 第 {trip_idx} 次往返")
            print(f"  ▶ 进度: {temp_ptr}/{total_cnt} | 装载: {tw:.1f}kg | 返回: {int(res['end_t']):02d}:{int(res['end_t']%1*60):02d}")
            print(f"  ▶ 路径: 0 -> {' -> '.join(map(str, res['path']))} -> 0")
            print("-" * 50)
            
            v['history'].append(res)
            v['ready'] = res['end_t'] # 更新就绪时间，这台车下次还能用！
            o_ptr = temp_ptr
        else:
            v['ready'] = 24.0 # 这台车今天干不完这趟了，强制收班

    # =================================================================
    # 5. 最终报表展示复用率
    # =================================================================
    print("\n" + "="*20 + " 车辆复用统计 " + "="*20)
    reused_count = 0
    for v in fleet:
        trips = len(v['history'])
        if trips > 0:
            if trips > 1: reused_count += 1
            print(f"车辆 {v['id']}: 今日执行 {trips} 个航次")
    print(f"\n复用车辆数: {reused_count} 台")

if __name__ == "__main__":
    run_optimized_simulation()