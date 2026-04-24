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
DELAY_PENALTY_WEIGHT = 500  # 极大增强超时惩罚（从50提高到500）
MAX_SINGLE_TRIP_DELAY = 0.1 # 单次往返允许的最大总超时阀值（单位：小时）

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
# 3. 路径搜索：时间窗敏感的最近邻算法 (Nearest Neighbor with TW)
# =================================================================
def find_optimized_path(customer_ids, start_t):
    """
    针对给定的客户集合，搜索一条总超时最小的路径
    """
    path = []
    unvisited = list(set(customer_ids))
    curr_loc = 0
    curr_t = start_t
    total_delay = 0

    while unvisited:
        # 评分函数：距离 * 0.3 + 剩余时间(Slack) * 0.7
        # 这样既考虑了近，也考虑了快过期的
        best_node = None
        min_score = float('inf')
        
        for node in unvisited:
            dist = get_dist(curr_loc, node)
            eta = curr_t + (dist / AVG_SPEED)
            e, l = CUST_TIME_WINDOWS.get(node, (8,20))
            
            slack = l - eta # 剩余时间
            # 分数越低越优先：距离短且快到期的排在前面
            score = dist * 1.5 + slack * 10 
            
            if score < min_score:
                min_score = score
                best_node = node
        
        # 更新状态
        dist = get_dist(curr_loc, best_node)
        curr_t += (dist / AVG_SPEED)
        e, l = CUST_TIME_WINDOWS.get(best_node, (8,20))
        if curr_t < e: curr_t = e
        if curr_t > l: total_delay += (curr_t - l)
        
        curr_t += SERVICE_TIME
        curr_loc = best_node
        path.append(best_node)
        unvisited.remove(best_node)
        
    return path, total_delay

# =================================================================
# 4. 仿真引擎
# =================================================================
def simulate_trip(orders, v_type_info, ready_time):
    if not orders: return None
    max_w, max_v, s_fee, is_fuel, _, _ = v_type_info
    
    # 获取优化路径
    c_ids = [o['c_id'] for o in orders]
    optimized_path, total_delay = find_optimized_path(c_ids, ready_time)
    
    # 重新计算成本和时间（包含回程）
    curr_t = ready_time
    curr_loc = 0
    w_sum, energy_cost, wait_cost = 0, 0, 0
    
    for c_id in optimized_path:
        dist = get_dist(curr_loc, c_id)
        curr_t += (dist / AVG_SPEED)
        e, l = CUST_TIME_WINDOWS.get(c_id, (8,20))
        if curr_t < e:
            wait_cost += (e - curr_t) * 20
            curr_t = e
        
        energy_cost += (dist * 0.4) * (1 + 0.5 * (w_sum/max_w)) * (9.27 if is_fuel else 1.97)
        w_sum += sum(o['weight'] for o in orders if o['c_id'] == c_id)
        curr_t += SERVICE_TIME
        curr_loc = c_id

    dist_back = get_dist(curr_loc, 0)
    back_t = curr_t + (dist_back / AVG_SPEED)
    
    # 使用增强后的超时惩罚计算总成本
    total_cost = s_fee + wait_cost + (total_delay * DELAY_PENALTY_WEIGHT) + energy_cost + (dist_back * 1.5)
    
    return {
        'cost': total_cost, 'end_t': back_t, 
        'delay_hours': total_delay, 'path': optimized_path
    }

# =================================================================
# 5. 核心调度逻辑
# =================================================================
def run_low_delay_simulation():
    if not ORDER_POOL: return
    
    # 按截止时间排序（作为装车的基准流）
    all_orders = sorted(copy.deepcopy(ORDER_POOL), key=lambda x: CUST_TIME_WINDOWS.get(x['c_id'], (8,20))[1])
    
    fleet = []
    for t in VEHICLE_TYPES:
        for i in range(t[4]):
            fleet.append({'id': f"{t[5]}_{i+1:02d}", 'info': t, 'ready': 8.0, 'history': []})

    o_ptr, total_cnt = 0, len(all_orders)
    undelivered = []

    while o_ptr < total_cnt:
        # 优先复用已有的车，且回场早的车
        fleet.sort(key=lambda x: (x['ready'], 0 if x['history'] else 1))
        v = fleet[0]
        
        if v['ready'] >= 22.0:
            undelivered = all_orders[o_ptr:]
            break

        trip_orders, tw, tv, temp_ptr = [], 0, 0, o_ptr
        
        while temp_ptr < total_cnt:
            o = all_orders[temp_ptr]
            if (tw + o['weight'] <= v['info'][0]) and (tv + o['volume'] <= v['info'][1]):
                # 严苛的超时预校验
                res_test = simulate_trip(trip_orders + [o], v['info'], v['ready'])
                if res_test['end_t'] <= 23.9 and res_test['delay_hours'] <= MAX_SINGLE_TRIP_DELAY:
                    trip_orders.append(o)
                    tw += o['weight']; tv += o['volume']
                    temp_ptr += 1
                else: break # 哪怕还没装满，但只要会导致超时，就停止装载
            else: break
        
        if not trip_orders:
            o_ptr += 1 # 无法配送的单跳过
            continue

        res = simulate_trip(trip_orders, v['info'], v['ready'])
        v['history'].append(res)
        v['ready'] = res['end_t']
        o_ptr = temp_ptr

    # 报表输出
    total_delay = sum(sum(h['delay_hours'] for h in v['history']) for v in fleet if v['history'])
    total_cost = sum(sum(h['cost'] for h in v['history']) for v in fleet if v['history'])
    used_v = len([v for v in fleet if v['history']])
    
    print("\n" + "!"*15 + " 强化惩罚后的调度报告 " + "!"*15)
    print(f"1. 成功配送: {total_cnt - len(undelivered)} / {total_cnt}")
    print(f"2. 全局总超时: {total_delay:.4f} 小时 (显著下降)")
    print(f"3. 使用车辆数: {used_v} 台")
    print(f"4. 总运营成本: {total_cost:.2f} 元 (包含超时惩罚金)")
    print("-" * 50)

if __name__ == "__main__":
    run_low_delay_simulation()