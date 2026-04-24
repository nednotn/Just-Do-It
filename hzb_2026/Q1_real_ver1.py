import numpy as np
import pandas as pd
import random
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
    """将多种格式的时间转换为 24 小时制的浮点数"""
    if isinstance(time_val, (int, float)): 
        return float(time_val)
    time_str = str(time_val).strip()
    try:
        if ':' in time_str:
            h, m = time_str.split(':')
            return int(h) + int(m) / 60.0
        return float(time_str)
    except:
        return 8.0  # 转换失败默认返回 8:00

# =================================================================
# 2. 数据加载逻辑 (带进度提示)
# =================================================================
def load_all_resources(order_file, window_file, dist_file):
    """一次性加载所有外部数据，并实时打印进度"""
    
    # 1. 加载订单数据
    print(f"1/3 正在加载订单文件: {order_file} ...", end=" ", flush=True)
    df_orders = pd.read_excel(order_file)
    df_orders.columns = [c.strip() for c in df_orders.columns]
    df_orders = df_orders[df_orders['目标客户编号'] > 0]
    orders = [{
        'o_id': r['订单编号'], 'c_id': int(r['目标客户编号']),
        'weight': float(r['重量']), 'volume': float(r['体积'])
    } for _, r in df_orders.iterrows()]
    print(f"完成 (共 {len(orders)} 条有效订单)")

    # 2. 加载时间窗数据
    print(f"2/3 正在加载时间窗文件: {window_file} ...", end=" ", flush=True)
    df_windows = pd.read_excel(window_file)
    df_windows.columns = [c.strip() for c in df_windows.columns]
    time_windows = {int(r['客户编号']): (time_to_float(r['开始时间']), time_to_float(r['结束时间'])) 
                    for _, r in df_windows.iterrows()}
    # 补齐 0-98 默认值
    for i in range(101): # 适当扩大范围确保覆盖
        if i not in time_windows: time_windows[i] = (8.0, 20.0)
    print("完成")

    # 3. 加载距离矩阵数据
    print(f"3/3 正在加载距离矩阵文件: {dist_file} (解析中)...", end=" ", flush=True)
    dist_df = pd.read_excel(dist_file, index_col=0)
    dist_matrix = dist_df.values
    print(f"完成 (矩阵尺寸: {dist_matrix.shape[0]}x{dist_matrix.shape[1]})")

    print("-" * 60)
    print("所有资源已成功进入内存，准备开始仿真计算...")
    print("-" * 60)

    return orders, time_windows, dist_matrix

# 全局变量初始化
try:
    ORDER_POOL, CUST_TIME_WINDOWS, DIST_MATRIX = load_all_resources('订单信息.xlsx', '时间窗.xlsx', '距离矩阵.xlsx')
except Exception as e:
    print(f"\n[错误] 数据初始化失败，请检查文件名或Excel列名是否正确: {e}")
    exit()

# =================================================================
# 3. 仿真引擎核心
# =================================================================
def get_dist(i, j):
    """从内存中快速索引距离，处理异常索引和空值"""
    try:
        val = DIST_MATRIX[int(i)][int(j)]
        return float(val) if not pd.isna(val) else 10.0
    except:
        return 10.0

def simulate_trip(orders, v_type_info, ready_time):
    max_w, max_v, s_fee, is_fuel, _, _ = v_type_info
    # 按时间窗起始时间对停靠点排序
    stops = sorted(list(set(o['c_id'] for o in orders)), key=lambda x: CUST_TIME_WINDOWS[x][0]) 
    
    # 智能推算最晚出发时间
    travel_to_first = get_dist(0, stops[0]) / 35.0
    actual_dep = max(ready_time, CUST_TIME_WINDOWS[stops[0]][0] - travel_to_first, 8.0)
    
    curr_t, curr_loc, w_sum = actual_dep, 0, 0
    wait_cost, delay_cost, energy_cost = 0, 0, 0
    
    for c_id in stops:
        dist = get_dist(curr_loc, c_id)
        curr_t += (dist / 35.0) # 行驶时间
        
        e, l = CUST_TIME_WINDOWS[c_id]
        if curr_t < e:
            wait_cost += (e - curr_t) * 20 # 等待成本
            curr_t = e 
        elif curr_t > l:
            delay_cost += (curr_t - l) * 50 # 迟到惩罚
            
        this_w = sum(o['weight'] for o in orders if o['c_id'] == c_id)
        # 能耗计算逻辑
        price = 9.27 if is_fuel else 1.97
        energy_cost += (dist * 0.4) * (1 + 0.5 * (w_sum/max_w)) * price
        
        w_sum += this_w
        curr_t += 20/60 # 假设每个客户服务20分钟
        curr_loc = c_id

    # 计算返回仓库
    dist_back = get_dist(curr_loc, 0)
    back_t = curr_t + (dist_back / 35.0)
    total_cost = s_fee + wait_cost + delay_cost + energy_cost + (dist_back * 1.5)
    
    return {
        'cost': total_cost,
        'wait_penalty': wait_cost,
        'delay_penalty': delay_cost,
        'end_t': back_t + 0.5, # 卸货清扫半小时
        'start_t': actual_dep,
        'w_rate': w_sum / max_w
    }

# =================================================================
# 4. 调度管理与执行
# =================================================================
def run_optimized_simulation():
    print(">>> 调度引擎初始化...")
    # 全局订单按时间窗排序，实现贪婪装载
    all_orders = sorted(copy.deepcopy(ORDER_POOL), key=lambda x: CUST_TIME_WINDOWS[x['c_id']][0])
    
    # 构建车队
    fleet = []
    for t in VEHICLE_TYPES:
        for i in range(t[4]):
            fleet.append({'id': f"{t[5]}_{i+1:02d}", 'info': t, 'ready': 8.0, 'history': []})

    o_ptr = 0
    total_cnt = len(all_orders)
    print(f">>> 准备处理 {total_cnt} 个订单，计算开始...\n")

    while o_ptr < len(all_orders):
        # 监控计算进度
        if o_ptr % 100 == 0:
            print(f"正在计算: 已完成订单 {o_ptr}/{total_cnt} (进度: {o_ptr/total_cnt:.1%})")

        # 选出最早空闲的车辆
        fleet.sort(key=lambda x: x['ready'])
        v = fleet[0]
        
        # 尝试装载当前订单及后续可容纳订单
        trip_orders, tw, tv, temp_ptr = [], 0, 0, o_ptr
        v_max_w, v_max_v = v['info'][0], v['info'][1]
        
        while temp_ptr < len(all_orders):
            o = all_orders[temp_ptr]
            if (tw + o['weight'] <= v_max_w) and (tv + o['volume'] <= v_max_v):
                trip_orders.append(o)
                tw += o['weight']
                tv += o['volume']
                temp_ptr += 1
            else:
                break
        
        if not trip_orders: # 防御性跳过异常订单
            o_ptr += 1
            continue

        # 执行仿真
        res = simulate_trip(trip_orders, v['info'], v['ready'])
        
        # 如果当日能跑完则记录，否则该车标记为今日饱和
        if res['end_t'] <= 23.5:
            v['history'].append(res)
            v['ready'] = res['end_t']
            o_ptr = temp_ptr
        else:
            v['ready'] = 24.0

    print("-" * 60)
    print("计算全部完成！正在汇总报表数据...")
    print("-" * 60)

    # =================================================================
    # 5. 结果可视化输出
    # =================================================================
    print(f"\n{'车辆ID':<10} | {'航次数':<4} | {'首班出发':<5} | {'末班返回':<5} | {'早到罚金':<7} | {'超时罚金':<7} | {'装载率'}")
    print("-" * 90)
    
    total_wait, total_delay, total_cost = 0, 0, 0
    for v in sorted(fleet, key=lambda x: x['id']):
        if not v['history']: continue
        
        v_wait = sum(h['wait_penalty'] for h in v['history'])
        v_delay = sum(h['delay_penalty'] for h in v['history'])
        v_cost = sum(h['cost'] for h in v['history'])
        v_load = np.mean([h['w_rate'] for h in v['history']])
        
        total_wait += v_wait
        total_delay += v_delay
        total_cost += v_cost
        
        h1, hn = v['history'][0], v['history'][-1]
        print(f"{v['id']:<10} | {len(v['history']):<6} | "
              f"{int(h1['start_t']):02d}:{int(h1['start_t']%1*60):02d} | "
              f"{int(hn['end_t']):02d}:{int(hn['end_t']%1*60):02d} | "
              f"{v_wait:>8.1f} | {v_delay:>8.1f} | {v_load:>6.1%}")

    print("-" * 90)
    print(f"系统汇总指标:")
    print(f"1. 成功调度订单总数: {o_ptr} / {len(ORDER_POOL)}")
    print(f"2. 累计早到等待成本: {total_wait:.2f} 元")
    print(f"3. 累计超时延迟惩罚: {total_delay:.2f} 元")
    print(f"4. 包含罚金的总运营成本: {total_cost:.2f} 元")

if __name__ == "__main__":
    run_optimized_simulation()