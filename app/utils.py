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

def discretize_concrete_core_into_rings(diameter, thickness, thermal_data, fire_exposure_time_sec, num_rings=7, ring_thicknesses=None):
    if not thermal_data:
        return []
        
    # Находим подходящую запись температурных данных
    suitable_records = [r for r in thermal_data if isinstance(r.get('time_minutes'), (int, float)) and r.get('time_minutes', -1) <= fire_exposure_time_sec]
    if suitable_records:
        thermal_record = max(suitable_records, key=lambda x: x.get('time_minutes', -1))
    else:
        all_time_records = [r for r in thermal_data if isinstance(r.get('time_minutes'), (int, float))]
        if all_time_records:
            thermal_record = min(all_time_records, key=lambda x: x.get('time_minutes', float('inf')))
        else:
            thermal_record = None
            
    # Радиусы
    column_radius_mm = diameter / 2.0
    concrete_core_outer_radius_mm = column_radius_mm - thickness
    
    # Если толщины не заданы, делим равномерно
    if ring_thicknesses is None:
        total_thickness = concrete_core_outer_radius_mm
        ring_thicknesses = [total_thickness / num_rings] * num_rings
    
    rings = []
    current_outer_radius = concrete_core_outer_radius_mm
    
    for i in range(num_rings):
        # Определяем толщину текущего кольца
        if i < len(ring_thicknesses) and ring_thicknesses[i] is not None:
            thickness_mm = ring_thicknesses[i]
        else:
            # Если толщина не задана, используем оставшееся пространство
            thickness_mm = current_outer_radius
            
        # Вычисляем внутренний радиус
        inner_radius = max(0.0, current_outer_radius - thickness_mm)
        
        # Вычисляем площадь кольца
        area = math.pi * (current_outer_radius**2 - inner_radius**2) if current_outer_radius > inner_radius else 0.0
        
        # Определяем температуру для кольца
        temp = None
        if thermal_record:
            if i == 0:  # Б1
                temp = thermal_record.get('temp_t2')
            elif i == 1:  # Б2
                temp = thermal_record.get('temp_t3')
            elif i == 2:  # Б3
                temp = thermal_record.get('temp_t5')
            elif i == 3:  # Б4
                temp = thermal_record.get('temp_t6')
            elif i == 4:  # Б5
                temp = thermal_record.get('temp_t7')
            elif i == 5:  # Б6
                temp = thermal_record.get('temp_t8')
            elif i == 6:  # Б7
                temp = thermal_record.get('temp_t9')
        
        rings.append({
            'outer_radius_mm': current_outer_radius,
            'inner_radius_mm': inner_radius,
            'area_mm2': area,
            'temperature_celsius': temp
        })
        
        # Обновляем внешний радиус для следующего кольца
        current_outer_radius = inner_radius
        
    return rings

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

def calculate_steel_ring(diameter, thickness, thermal_data, fire_exposure_time_sec, rebar_diameter):
    if not thermal_data:
        return None
        
    # Находим подходящую запись температурных данных
    suitable_records = [r for r in thermal_data if isinstance(r.get('time_minutes'), (int, float)) and r.get('time_minutes', -1) <= fire_exposure_time_sec]
    if suitable_records:
        thermal_record = max(suitable_records, key=lambda x: x.get('time_minutes', -1))
    else:
        all_time_records = [r for r in thermal_data if isinstance(r.get('time_minutes'), (int, float))]
        if all_time_records:
            thermal_record = min(all_time_records, key=lambda x: x.get('time_minutes', float('inf')))
        else:
            thermal_record = None
            
    # Радиусы
    column_radius_mm = diameter / 2.0
    steel_ring_outer_radius_mm = column_radius_mm
    steel_ring_inner_radius_mm = column_radius_mm - thickness
    
    # Площадь кольца
    area = math.pi * (steel_ring_outer_radius_mm**2 - steel_ring_inner_radius_mm**2)
    
    # Момент инерции кольца
    I_ring = (math.pi / 4) * (steel_ring_outer_radius_mm**4 - steel_ring_inner_radius_mm**4)
    
    # Момент инерции арматуры (формула из Excel)
    rebar_distance_mm = 210  # расстояние от центра до арматуры
    sin_45 = math.sin(math.radians(45))
    I_rebar = (2 * (math.pi * rebar_diameter * rebar_diameter / 4) * (rebar_distance_mm**2 + (rebar_distance_mm * sin_45)**2 + (rebar_distance_mm * sin_45)**2)) * 1e-12
    
    # Общий момент инерции
    I_total = I_ring + I_rebar
    
    # Определяем температуру
    temp = thermal_record.get('temp_t1') if thermal_record else None
    
    return {
        'outer_radius_mm': steel_ring_outer_radius_mm,
        'inner_radius_mm': steel_ring_inner_radius_mm,
        'area_mm2': area,
        'moment_of_inertia_mm4': I_total,
        'temperature_celsius': temp
    } 