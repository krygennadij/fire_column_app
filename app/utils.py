import math
# Удаляем Session и ThermalData, так как работаем с JSON

def calc_section(diameter, thickness):
    D = diameter / 1000
    t = thickness / 1000
    A_steel = math.pi * ((D/2)**2 - ((D/2)-t)**2)
    A_conc = math.pi * ((D/2-t)**2)
    return A_steel, A_conc

def calc_capacity(A_steel, A_conc, steel_strength, concrete_strength):
    return concrete_strength * A_conc * 1e6 + steel_strength * A_steel * 1e6 

def discretize_concrete_core_into_rings(
    outer_column_diameter_mm: float, 
    steel_wall_thickness_mm: float,
    thermal_data_list: list[dict], 
    fire_exposure_time_sec: float,
    num_rings: int = 5,
    ring_thicknesses: list[float] = [10, 20, 20, 20, None]
) -> list[dict]:
    print(f"--- Utils Debug: discretize_concrete_core_into_rings called ---")
    print(f"--- Utils Debug: fire_exposure_time_sec = {fire_exposure_time_sec} ---")
    if thermal_data_list:
        print(f"--- Utils Debug: thermal_data_list contains {len(thermal_data_list)} records. First record keys: {thermal_data_list[0].keys() if thermal_data_list else 'N/A'} ---")
    else:
        print("--- Utils Debug: thermal_data_list is empty. ---")

    column_radius_mm = outer_column_diameter_mm / 2.0
    concrete_core_outer_radius_mm = column_radius_mm - steel_wall_thickness_mm
    rings_details = []
    current_outer_r = concrete_core_outer_radius_mm
    if concrete_core_outer_radius_mm <= 1e-9: 
        current_outer_r = 0.0 

    # Создаем кольца с заданными толщинами
    for i in range(num_rings):
        ring_num = i + 1
        outer_r = current_outer_r
        inner_r = 0.0
        actual_t = 0.0
        area = 0.0
        
        if current_outer_r > 1e-9:
            target_t = ring_thicknesses[i]
            if target_t is None:  # Для последнего кольца берем оставшуюся толщину
                actual_t = current_outer_r
            else:
                actual_t = min(target_t, current_outer_r)
            inner_r = current_outer_r - actual_t
            if outer_r > inner_r: 
                area = math.pi * (outer_r**2 - inner_r**2)
                
        rings_details.append({
            'ring_number': ring_num,
            'outer_radius_mm': outer_r,
            'inner_radius_mm': inner_r,
            'thickness_mm': actual_t,
            'area_mm2': area,
            'temperature_celsius': None 
        })
        current_outer_r = inner_r

    thermal_record = None
    if thermal_data_list:
        suitable_records = [r for r in thermal_data_list if isinstance(r.get('time_minutes'), (int, float)) and r.get('time_minutes', -1) <= fire_exposure_time_sec]
        print(f"--- Utils Debug: Found {len(suitable_records)} suitable records with time <= {fire_exposure_time_sec} сек ---")
        if suitable_records:
            thermal_record = max(suitable_records, key=lambda x: x.get('time_minutes', -1))
            print(f"--- Utils Debug: Selected record by MAX time: {thermal_record.get('time_minutes')} сек ---")
        else:
            all_time_records = [r for r in thermal_data_list if isinstance(r.get('time_minutes'), (int, float))]
            if all_time_records:
                 thermal_record = min(all_time_records, key=lambda x: x.get('time_minutes', float('inf'))) 
                 print(f"--- Utils Debug: No records <= time, selected record by MIN time: {thermal_record.get('time_minutes')} сек ---")
            else:
                print("--- Utils Debug: No records with valid time_minutes found in thermal_data_list. ---")
    
    if thermal_record:
        print(f"--- Utils Debug: Using thermal data for time {thermal_record.get('time_minutes')} сек. Record content: {thermal_record} ---")
        temps_keys_for_rings = [f'temp_t{i}' for i in range(2, 7)]  # Изменено на 5 колец
        for i in range(len(rings_details)):
            if i < len(temps_keys_for_rings):
                temp_key = temps_keys_for_rings[i]
                temp_value = thermal_record.get(temp_key)
                print(f"--- Utils Debug: Ring {i+1}, temp_key '{temp_key}', value from record: {temp_value} (type: {type(temp_value)}) ---")
                if isinstance(temp_value, (int, float)):
                    rings_details[i]['temperature_celsius'] = float(temp_value)
                else:
                    rings_details[i]['temperature_celsius'] = None
            else:
                break 
    else:
        print(f"--- Utils Debug: No suitable thermal data found in JSON for time {fire_exposure_time_sec} сек. Temperatures will be None. ---")

    return rings_details

def steel_ring_area(diameter_mm, thickness_mm):
    R_out = diameter_mm / 2
    R_in = R_out - thickness_mm
    return math.pi * (R_out**2 - R_in**2)  # мм²

def steel_working_condition_coeff(temp_celsius):
    table = [
        (20, 1.00), (100, 1.00), (200, 0.90), (300, 0.80), (400, 0.70),
        (500, 0.60), (600, 0.31), (700, 0.13), (800, 0.09), (900, 0.0675),
        (1000, 0.0450), (1100, 0.0225), (1200, 0.0),
    ]
    if temp_celsius <= table[0][0]:
        return table[0][1]
    if temp_celsius >= table[-1][0]:
        return table[-1][1]
    for i in range(1, len(table)):
        t0, k0 = table[i-1]
        t1, k1 = table[i]
        if t0 <= temp_celsius <= t1:
            return k0 + (k1 - k0) * (temp_celsius - t0) / (t1 - t0)
    return table[-1][1] 

def concrete_working_condition_coeff(temp_celsius):
    table = [
        (20, 1.00), (100, 1.00), (200, 0.95), (300, 0.85), (400, 0.75),
        (500, 0.60), (600, 0.45), (700, 0.30), (800, 0.15), (900, 0.08),
        (1000, 0.04), (1100, 0.01), (1200, 0.0),
    ]
    if temp_celsius <= table[0][0]:
        return table[0][1]
    if temp_celsius >= table[-1][0]:
        return table[-1][1]
    for i in range(1, len(table)):
        t0, k0 = table[i-1]
        t1, k1 = table[i]
        if t0 <= temp_celsius <= t1:
            return k0 + (k1 - k0) * (temp_celsius - t0) / (t1 - t0)
    return table[-1][1] 

def concrete_strain_by_temp(temp_c):
    """
    Интерполяция деформации бетона по температуре (см. таблицу в ТЗ).
    Возвращает значение в 10^-3 (тысячных долях).
    """
    table = [
        (20, 2.5),
        (100, 4.0),
        (200, 5.5),
        (300, 7.0),
        (400, 10.0),
        (500, 15.0),
        (600, 25.0),
        (700, 25.0),
        (800, 25.0),
        (900, 25.0),
        (1000, 25.0),
        (1100, 25.0),
        (1200, None),
    ]
    if temp_c < 20:
        return 2.5
    for i in range(1, len(table)):
        t0, e0 = table[i-1]
        t1, e1 = table[i]
        if temp_c <= t1:
            if e1 is None:
                return None
            return e0 + (e1 - e0) * (temp_c - t0) / (t1 - t0)
    return None 