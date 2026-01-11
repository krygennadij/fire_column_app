"""
Вспомогательные функции для расчётов огнестойкости.

Содержит функции для:
- Расчёта геометрических параметров сечения
- Дискретизации бетонного ядра на кольца
- Определения коэффициентов работы материалов при температуре
- Расчёта деформаций бетона
"""

import math
from typing import Dict, List, Optional
from .config import MATERIAL_CONSTANTS


def calc_section(diameter_mm: float, thickness_mm: float) -> tuple[float, float]:
    """
    Расчёт площадей стального и бетонного сечений.

    Args:
        diameter_mm: Наружный диаметр колонны в мм
        thickness_mm: Толщина стенки в мм

    Returns:
        Кортеж (A_steel_m2, A_concrete_m2):
        - A_steel_m2: Площадь стального кольца в м²
        - A_concrete_m2: Площадь бетонного ядра в м²
    """
    D_m = diameter_mm / 1000
    t_m = thickness_mm / 1000

    # Площадь стального кольца
    A_steel = math.pi * ((D_m/2)**2 - ((D_m/2) - t_m)**2)

    # Площадь бетонного ядра
    A_conc = math.pi * ((D_m/2 - t_m)**2)

    return A_steel, A_conc


def calc_capacity(
    A_steel_m2: float,
    A_conc_m2: float,
    steel_strength_mpa: float,
    concrete_strength_mpa: float
) -> float:
    """
    Расчёт несущей способности сечения (без учёта температуры).

    Args:
        A_steel_m2: Площадь стали в м²
        A_conc_m2: Площадь бетона в м²
        steel_strength_mpa: Расчётное сопротивление стали в МПа
        concrete_strength_mpa: Расчётное сопротивление бетона в МПа

    Returns:
        Несущая способность в Н
    """
    return concrete_strength_mpa * A_conc_m2 * 1e6 + steel_strength_mpa * A_steel_m2 * 1e6


def discretize_concrete_core_into_rings(
    diameter_mm: float,
    thickness_mm: float,
    thermal_data: List[Dict],
    fire_exposure_time_sec: float,
    num_rings: int = 7,
    ring_thicknesses: Optional[List[Optional[float]]] = None
) -> List[Dict]:
    """
    Дискретизация бетонного ядра на концентрические кольца.

    Разбивает бетонное ядро на заданное количество колец и присваивает
    каждому кольцу температуру на основе температурных данных.

    Args:
        diameter_mm: Наружный диаметр колонны в мм
        thickness_mm: Толщина стального кольца в мм
        thermal_data: Список температурных данных
        fire_exposure_time_sec: Время пожара в секундах
        num_rings: Количество колец для дискретизации
        ring_thicknesses: Список толщин колец в мм (от внешнего к внутреннему).
                          None для последнего кольца означает "занять весь остаток"

    Returns:
        Список словарей с параметрами колец:
        - outer_radius_mm: Внешний радиус кольца в мм
        - inner_radius_mm: Внутренний радиус кольца в мм
        - area_mm2: Площадь кольца в мм²
        - temperature_celsius: Температура кольца в °C
    """
    if not thermal_data:
        return []

    # Находим подходящую запись температурных данных
    suitable_records = [
        r for r in thermal_data
        if isinstance(r.get('time_minutes'), (int, float))
        and r.get('time_minutes', -1) <= fire_exposure_time_sec
    ]

    if suitable_records:
        thermal_record = max(suitable_records, key=lambda x: x.get('time_minutes', -1))
    else:
        all_time_records = [
            r for r in thermal_data
            if isinstance(r.get('time_minutes'), (int, float))
        ]
        if all_time_records:
            thermal_record = min(all_time_records, key=lambda x: x.get('time_minutes', float('inf')))
        else:
            thermal_record = None

    # Радиусы
    column_radius_mm = diameter_mm / 2.0
    concrete_core_outer_radius_mm = column_radius_mm - thickness_mm

    # Если толщины не заданы, делим равномерно
    if ring_thicknesses is None:
        total_thickness = concrete_core_outer_radius_mm
        ring_thicknesses = [total_thickness / num_rings] * num_rings

    rings = []
    current_outer_radius = concrete_core_outer_radius_mm

    for i in range(num_rings):
        # Определяем толщину текущего кольца
        if i < len(ring_thicknesses) and ring_thicknesses[i] is not None:
            thickness_ring_mm = ring_thicknesses[i]
        else:
            # Если толщина не задана, используем оставшееся пространство
            thickness_ring_mm = current_outer_radius

        # Вычисляем внутренний радиус
        inner_radius = max(0.0, current_outer_radius - thickness_ring_mm)

        # Вычисляем площадь кольца
        area = (
            math.pi * (current_outer_radius**2 - inner_radius**2)
            if current_outer_radius > inner_radius
            else 0.0
        )

        # Определяем температуру для кольца на основе номера
        # Маппинг: Б1->temp_t2, Б2->temp_t3, Б3->temp_t5, Б4->temp_t6,
        #          Б5->temp_t7, Б6->temp_t8, Б7->temp_t9
        temp = None
        if thermal_record:
            temperature_mapping = {
                0: 'temp_t2',  # Б1
                1: 'temp_t3',  # Б2
                2: 'temp_t5',  # Б3
                3: 'temp_t6',  # Б4
                4: 'temp_t7',  # Б5
                5: 'temp_t8',  # Б6
                6: 'temp_t9',  # Б7
            }
            temp_key = temperature_mapping.get(i)
            if temp_key:
                temp = thermal_record.get(temp_key)

        rings.append({
            'outer_radius_mm': current_outer_radius,
            'inner_radius_mm': inner_radius,
            'area_mm2': area,
            'temperature_celsius': temp
        })

        # Обновляем внешний радиус для следующего кольца
        current_outer_radius = inner_radius

    return rings


def steel_ring_area(diameter_mm: float, thickness_mm: float) -> float:
    """
    Расчёт площади стального кольца.

    Args:
        diameter_mm: Наружный диаметр колонны в мм
        thickness_mm: Толщина стенки в мм

    Returns:
        Площадь стального кольца в мм²
    """
    R_out = diameter_mm / 2
    R_in = R_out - thickness_mm
    return math.pi * (R_out**2 - R_in**2)


def steel_working_condition_coeff(temp_celsius: float) -> float:
    """
    Коэффициент условий работы стали при повышенных температурах γ_st.

    Источник: СП 468.1325800.2019 "Конструкции стальные.
    Правила проектирования. Расчёт конструкций на огнестойкость"
    Таблица 5.1

    Применяется линейная интерполяция между табличными значениями.

    Args:
        temp_celsius: Температура стали в °C

    Returns:
        Коэффициент условий работы γ_st (безразмерный)
    """
    # Табличные значения из СП 468.1325800.2019
    table = [
        (20, 1.00),
        (100, 1.00),
        (200, 0.90),
        (300, 0.80),
        (400, 0.70),
        (500, 0.60),
        (600, 0.31),
        (700, 0.13),
        (800, 0.09),
        (900, 0.0675),
        (1000, 0.0450),
        (1100, 0.0225),
        (1200, 0.0),
    ]

    # Проверка границ
    if temp_celsius <= table[0][0]:
        return table[0][1]
    if temp_celsius >= table[-1][0]:
        return table[-1][1]

    # Линейная интерполяция
    for i in range(1, len(table)):
        t0, k0 = table[i-1]
        t1, k1 = table[i]
        if t0 <= temp_celsius <= t1:
            return k0 + (k1 - k0) * (temp_celsius - t0) / (t1 - t0)

    return table[-1][1]


def concrete_working_condition_coeff(temp_celsius: float) -> float:
    """
    Коэффициент условий работы бетона при повышенных температурах γ_bt.

    Источник: СП 468.1325800.2019
    Таблица для бетона при огневом воздействии

    Применяется линейная интерполяция между табличными значениями.

    Args:
        temp_celsius: Температура бетона в °C

    Returns:
        Коэффициент условий работы γ_bt (безразмерный)
    """
    # Табличные значения из СП 468.1325800.2019
    table = [
        (20, 1.00),
        (100, 1.00),
        (200, 0.95),
        (300, 0.85),
        (400, 0.75),
        (500, 0.60),
        (600, 0.45),
        (700, 0.30),
        (800, 0.15),
        (900, 0.08),
        (1000, 0.04),
        (1100, 0.01),
        (1200, 0.0),
    ]

    # Проверка границ
    if temp_celsius <= table[0][0]:
        return table[0][1]
    if temp_celsius >= table[-1][0]:
        return table[-1][1]

    # Линейная интерполяция
    for i in range(1, len(table)):
        t0, k0 = table[i-1]
        t1, k1 = table[i]
        if t0 <= temp_celsius <= t1:
            return k0 + (k1 - k0) * (temp_celsius - t0) / (t1 - t0)

    return table[-1][1]


def concrete_strain_by_temp(temp_celsius: float) -> Optional[float]:
    """
    Деформация бетона при заданной температуре ε_yn,t.

    Источник: Нормативные данные для расчёта бетонных конструкций
    при пожаре.

    Применяется линейная интерполяция между табличными значениями.

    Args:
        temp_celsius: Температура бетона в °C

    Returns:
        Деформация в тысячных долях (×10⁻³) или None при T≥1200°C
    """
    # Табличные значения деформаций
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
        (1200, None),  # При 1200°C бетон полностью разрушен
    ]

    # Проверка нижней границы
    if temp_celsius < 20:
        return 2.5

    # Линейная интерполяция
    for i in range(1, len(table)):
        t0, e0 = table[i-1]
        t1, e1 = table[i]
        if temp_celsius <= t1:
            if e1 is None:
                return None
            return e0 + (e1 - e0) * (temp_celsius - t0) / (t1 - t0)

    return None


def calculate_steel_ring(
    diameter_mm: float,
    thickness_mm: float,
    thermal_data: List[Dict],
    fire_exposure_time_sec: float,
    rebar_diameter_mm: int
) -> Optional[Dict]:
    """
    Расчёт параметров стального кольца.

    Args:
        diameter_mm: Наружный диаметр колонны в мм
        thickness_mm: Толщина стенки в мм
        thermal_data: Список температурных данных
        fire_exposure_time_sec: Время пожара в секундах
        rebar_diameter_mm: Диаметр арматуры в мм

    Returns:
        Словарь с параметрами стального кольца или None:
        - outer_radius_mm: Внешний радиус
        - inner_radius_mm: Внутренний радиус
        - area_mm2: Площадь
        - moment_of_inertia_mm4: Момент инерции
        - temperature_celsius: Температура
    """
    if not thermal_data:
        return None

    # Находим подходящую запись температурных данных
    suitable_records = [
        r for r in thermal_data
        if isinstance(r.get('time_minutes'), (int, float))
        and r.get('time_minutes', -1) <= fire_exposure_time_sec
    ]

    if suitable_records:
        thermal_record = max(suitable_records, key=lambda x: x.get('time_minutes', -1))
    else:
        all_time_records = [
            r for r in thermal_data
            if isinstance(r.get('time_minutes'), (int, float))
        ]
        if all_time_records:
            thermal_record = min(all_time_records, key=lambda x: x.get('time_minutes', float('inf')))
        else:
            thermal_record = None

    # Радиусы стального кольца
    column_radius_mm = diameter_mm / 2.0
    steel_ring_outer_radius_mm = column_radius_mm
    steel_ring_inner_radius_mm = column_radius_mm - thickness_mm

    # Площадь кольца
    area = math.pi * (steel_ring_outer_radius_mm**2 - steel_ring_inner_radius_mm**2)

    # Момент инерции кольца
    I_ring = (math.pi / 4) * (steel_ring_outer_radius_mm**4 - steel_ring_inner_radius_mm**4)

    # Момент инерции арматуры (формула из проектной документации)
    # Расстояние от центра до арматуры с учётом защитного слоя
    rebar_distance_mm = (
        column_radius_mm - thickness_mm
        - MATERIAL_CONSTANTS.REBAR_COVER_MM
        - (rebar_diameter_mm / 2)
    )

    sin_45 = math.sin(math.radians(45))

    # Формула момента инерции для 8 стержней, расположенных по окружности
    I_rebar = (
        2 * (math.pi * rebar_diameter_mm * rebar_diameter_mm / 4)
        * (rebar_distance_mm**2 + (rebar_distance_mm * sin_45)**2 + (rebar_distance_mm * sin_45)**2)
    ) * 1e-12

    # Общий момент инерции
    I_total = I_ring + I_rebar

    # Определяем температуру стального кольца
    temp = thermal_record.get('temp_t1') if thermal_record else None

    return {
        'outer_radius_mm': steel_ring_outer_radius_mm,
        'inner_radius_mm': steel_ring_inner_radius_mm,
        'area_mm2': area,
        'moment_of_inertia_mm4': I_total,
        'temperature_celsius': temp
    }
