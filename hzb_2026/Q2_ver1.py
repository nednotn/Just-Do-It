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
DELAY_PENALTY_WEIGHT = 500  
# 适当放宽单次路径的超时阈值，以保证大规模订单的完成度
MAX_SINGLE_TRIP_DELAY = 0.5 

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
# 2. 数据加载与坐标处理
# =================================================================
def load_all_resources(order_file, window_file, dist_file, coord_file):
    try:
        # 1. 加载订单
        df_orders = pd.read_excel(order_file)
        df_orders.columns = [c.strip() for c in df_orders.columns]
        orders = [{
            'o_id': r['订单编号'], 'c_id': int(r['目标客户编号']),
            'weight': float(r['重量']), 'volume': float(r['体积'])
        } for _, r in df_orders.iterrows() if r['目标客户编号'] > 0]

        # 2. 加载时间窗
        df_windows = pd.read_excel(window_file)
        df_windows.columns = [c.strip() for c in df_windows.columns]
        time_windows = {int(r['客户编号']): (time_to_float(r['开始时间']), time_to_float(r['结束时间'])) 
                        for _, r in df_windows.iterrows()}
        
        # 3. 加载距离矩阵
        dist_df = pd.read_excel(dist_file, index_col=0)
        dist_matrix = dist_df.values

        # 4. 计算禁区客户 (距离原点 < 10km)
        df_coords = pd.read_excel(coord_file)
        ev_only_customers = set()
        for _, row in df_coords.iterrows():
            c_id = int(row['ID'])
            if c_id == 0: continue 
            x, y = float(row['X (km)']), float(row['Y (km)'])
            # 欧几里得距离计算
            if np.sqrt(x**2 + y**2) < 10:
                ev_only_customers.add(c_id)
        
        print(f"成功加载数据：{len(orders)}个订单，{len(ev_only_customers)}个禁区客户。")
        return orders, time_windows, dist_matrix, ev_only_customers
    except Exception as e:
        print(f"数据加载失败: {e}")
        return [], {}, None, set()

ORDER_POOL, CUST_TIME_WINDOWS, DIST_MATRIX, EV_ONLY_CUSTS = load_all_resources(
    '订单信息.xlsx', '时间窗.xlsx', '距离矩阵.xlsx', '客户坐标信息.xlsx'
)

def get_dist(i, j):
    try: return float(DIST_MATRIX[int(i)][int(j)])
    except: return 10.0

# =================================================================
# 3. 路径搜索
# =================================================================
def find_optimized_path(customer_ids, start_t):
    path = []
    unvisited = list(set(customer_ids))
    curr_loc = 0
    curr_t = start_t
    total_delay = 0

    while unvisited:
        best_node = None
        min_score = float('inf')
        for node in unvisited:
            dist = get_dist(curr_loc, node)
            eta = curr_t + (dist / AVG_SPEED)
            e, l = CUST_TIME_WINDOWS.get(node, (8,20))
            slack = l - eta
            # 评价函数：综合距离和紧急程度
            score = dist * 1.2 + slack * 10
            if score < min_score:
                min_score = score
                best_node = node
        
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
    
    c_ids = [o['c_id'] for o in orders]
    optimized_path, total_delay = find_optimized_path(c_ids, ready_time)
    
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
        
        # 简化能耗计算
        energy_cost += (dist * 0.4) * (1 + 0.5 * (w_sum/max_w)) * (9.27 if is_fuel else 1.97)
        w_sum += sum(o['weight'] for o in orders if o['c_id'] == c_id)
        curr_t += SERVICE_TIME
        curr_loc = c_id

    dist_back = get_dist(curr_loc, 0)
    back_t = curr_t + (dist_back / AVG_SPEED)
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
    
    # 排序订单：按截止时间排序
    all_orders = sorted(copy.deepcopy(ORDER_POOL), key=lambda x: CUST_TIME_WINDOWS.get(x['c_id'], (8,20))[1])
    
    fleet = []
    for t in VEHICLE_TYPES:
        for i in range(t[4]):
            fleet.append({'id': f"{t[5]}_{i+1:02d}", 'info': t, 'ready': 8.0, 'history': [], 'is_fuel': t[3]})

    delivered_ids = set()
    total_orders_cnt = len(all_orders)

    # 调度主循环
    while len(delivered_ids) < total_orders_cnt:
        # 选取最早可用的车
        fleet.sort(key=lambda x: (x['ready'], 0 if x['history'] else 1))
        v = fleet[0]
        
        if v['ready'] >= 22.0: # 超过22点不再派新单
            break

        trip_orders, tw, tv = [], 0, 0
        current_trip_oids = []
        
        # 遍历未配送订单
        for o in all_orders:
            if o['o_id'] in delivered_ids:
                continue
            
            # --- 硬约束：油车禁入 10km 禁区 ---
            if v['is_fuel'] and (o['c_id'] in EV_ONLY_CUSTS):
                continue
            
            # 容积和载重检查
            if (tw + o['weight'] <= v['info'][0]) and (tv + o['volume'] <= v['info'][1]):
                # 预仿真校验
                res_test = simulate_trip(trip_orders + [o], v['info'], v['ready'])
                # 如果加上这单后，回程不超时且延误在可接受范围内
                if res_test['end_t'] <= 23.9 and res_test['delay_hours'] <= MAX_SINGLE_TRIP_DELAY:
                    trip_orders.append(o)
                    tw += o['weight']
                    tv += o['volume']
                    current_trip_oids.append(o['o_id'])
                
                # 控制单次往返的订单数，避免路径过长导致后续大面积延误
                if len(trip_orders) >= 12:
                    break
        
        if not trip_orders:
            # 如果这辆车在本轮找不到任何可送的单子，时间步进，防止死循环
            v['ready'] += 0.25 
            # 检查是否所有车都无法工作
            if all(car['ready'] >= 22.0 for car in fleet):
                break
            continue

        # 正式记录这次配送
        res = simulate_trip(trip_orders, v['info'], v['ready'])
        v['history'].append(res)
        v['ready'] = res['end_t']
        for oid in current_trip_oids:
            delivered_ids.add(oid)

    # =================================================================
    # 6. 结果报表
    # =================================================================
    success_cnt = len(delivered_ids)
    all_history = [h for v in fleet for h in v['history']]
    total_delay = sum(h['delay_hours'] for h in all_history)
    total_cost = sum(h['cost'] for h in all_history)
    used_v = len([v for v in fleet if v['history']])
    
    print("\n" + "="*20 + " 最终调度报告 " + "="*20)
    print(f"1. 订单总量: {total_orders_cnt}")
    print(f"2. 成功配送: {success_cnt} ({(success_cnt/total_orders_cnt)*100:.2f}%)")
    print(f"3. 未能配送: {total_orders_cnt - success_cnt}")
    print(f"4. 全局总超时: {total_delay:.4f} 小时")
    print(f"5. 使用车辆数: {used_v} 台")
    print(f"6. 总运营成本: {total_cost:.2f} 元")
    print("="*54)

if __name__ == "__main__":
    run_low_delay_simulation()