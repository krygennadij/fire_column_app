"""
Расчётные функции для определения несущей способности колонны при пожаре.

Содержит функции для расчёта:
- Несущей способности для заданного времени
- Жёсткости сечения
- Критической силы
- Условной гибкости
"""

import math
from typing import Dict, List, Optional, Tuple
from .utils import (
    discretize_concrete_core_into_rings,
    steel_ring_area,
    steel_working_condition_coeff,
    concrete_working_condition_coeff,
    concrete_strain_by_temp
)
from .config import MATERIAL_CONSTANTS


def get_thermal_record_for_time(
    thermal_data: List[Dict],
    fire_exposure_time_sec: float
) -> Optional[Dict]:
    """
    Получить запись температурных данных для заданного времени.

    Выбирается запись с максимальным временем, не превышающим заданное.
    Если такой записи нет, выбирается запись с минимальным временем.

    Args:
        thermal_data: Список температурных данных
        fire_exposure_time_sec: Время пожара в секундах

    Returns:
        Словарь с температурными данными или None
    """
    if not thermal_data:
        return None

    # Фильтруем записи с корректным временем
    suitable_records = [
        r for r in thermal_data
        if isinstance(r.get('time_minutes'), (int, float))
        and r.get('time_minutes', -1) <= fire_exposure_time_sec
    ]

    if suitable_records:
        # Берём запись с максимальным временем
        return max(suitable_records, key=lambda x: x.get('time_minutes', -1))
    else:
        # Берём запись с минимальным временем
        all_time_records = [
            r for r in thermal_data
            if isinstance(r.get('time_minutes'), (int, float))
        ]
        if all_time_records:
            return min(all_time_records, key=lambda x: x.get('time_minutes', float('inf')))

    return None


def calculate_stiffness_for_time(
    diameter_mm: float,
    thickness_mm: float,
    thermal_data: List[Dict],
    fire_exposure_time_sec: float,
    concrete_strength_mpa: float,
    steel_elastic_modulus_mpa: float,
    use_reinforcement: bool = False,
    rebar_diameter_mm: int = 10,
    rebar_count: int = 8,
    num_rings: int = 7,
    ring_thicknesses: Optional[List[Optional[float]]] = None
) -> float:
    """
    Расчёт жёсткости сечения (EI) для заданного времени пожара.

    Args:
        diameter_mm: Наружный диаметр колонны в мм
        thickness_mm: Толщина стенки в мм
        thermal_data: Температурные данные
        fire_exposure_time_sec: Время пожара в секундах
        concrete_strength_mpa: Прочность бетона в МПа
        steel_elastic_modulus_mpa: Модуль упругости стали в МПа
        use_reinforcement: Учитывать ли армирование
        rebar_diameter_mm: Диаметр арматуры в мм
        rebar_count: Количество стержней
        num_rings: Количество бетонных колец
        ring_thicknesses: Толщины колец

    Returns:
        Полная жёсткость сечения в кН·м²
    """
    total_stiffness = 0.0

    # Получаем запись температурных данных
    thermal_record = get_thermal_record_for_time(thermal_data, fire_exposure_time_sec)

    # Разбиваем бетонное ядро на кольца
    concrete_rings = discretize_concrete_core_into_rings(
        diameter_mm, thickness_mm, thermal_data, fire_exposure_time_sec,
        num_rings, ring_thicknesses
    )

    # Суммируем жёсткости бетонных колец
    for ring in concrete_rings:
        R_out = ring['outer_radius_mm']
        R_in = ring['inner_radius_mm']
        I_ring = (math.pi / 4) * (R_out**4 - R_in**4) / 1e12  # м⁴

        if ring['temperature_celsius'] is not None:
            gamma_bt = concrete_working_condition_coeff(ring['temperature_celsius'])
            f_cd_fire = gamma_bt * concrete_strength_mpa
            strain = concrete_strain_by_temp(ring['temperature_celsius'])

            if strain and strain > 0:
                E_c_fire = f_cd_fire / (strain * 1e-3)  # МПа
                total_stiffness += I_ring * E_c_fire * 1e3  # кН·м²

    # Добавляем жёсткость стального кольца
    if thermal_record:
        temp_steel = thermal_record.get('temp_t1')
        if temp_steel is not None and isinstance(temp_steel, (int, float)):
            gamma_st = steel_working_condition_coeff(temp_steel)
            E_steel_fire = steel_elastic_modulus_mpa * gamma_st

            R_out_steel = diameter_mm / 2
            R_in_steel = R_out_steel - thickness_mm
            I_steel_ring = (math.pi / 4) * (R_out_steel**4 - R_in_steel**4) / 1e12  # м⁴

            total_stiffness += I_steel_ring * E_steel_fire * 1e3  # кН·м²

    # Добавляем жёсткость арматуры
    if use_reinforcement and thermal_record:
        temp_rebar = thermal_record.get('temp_t4')
        if temp_rebar is not None and isinstance(temp_rebar, (int, float)):
            gamma_st_rebar = steel_working_condition_coeff(temp_rebar)
            E_rebar_fire = steel_elastic_modulus_mpa * gamma_st_rebar

            # Расстояние от центра до арматуры (с учётом защитного слоя)
            rebar_distance_mm = (
                (diameter_mm / 2) - thickness_mm
                - MATERIAL_CONSTANTS.REBAR_COVER_MM
                - (rebar_diameter_mm / 2)
            )

            # Момент инерции одного стержня
            I_self_bar = (math.pi * rebar_diameter_mm**4) / 64

            # Площадь одного стержня
            rebar_area_one = (math.pi * rebar_diameter_mm**2) / 4

            # Формула для момента инерции арматуры:
            # I = 8·I_собств + 4·A_стержня·(R-a)²
            # где (R-a) - расстояние от центра до арматуры
            I_rebar = (8 * I_self_bar + 4 * rebar_area_one * rebar_distance_mm**2) * 1e-12  # м⁴

            total_stiffness += I_rebar * E_rebar_fire * 1e3  # кН·м²

    return total_stiffness


def calculate_capacity_for_time(
    diameter_mm: float,
    thickness_mm: float,
    thermal_data: List[Dict],
    fire_exposure_time_sec: float,
    steel_strength_mpa: float,
    concrete_strength_mpa: float,
    use_reinforcement: bool = False,
    rebar_diameter_mm: int = 10,
    rebar_count: int = 8,
    num_rings: int = 7,
    ring_thicknesses: Optional[List[Optional[float]]] = None
) -> float:
    """
    Расчёт несущей способности (без учёта гибкости) для заданного времени.

    Args:
        diameter_mm: Наружный диаметр колонны в мм
        thickness_mm: Толщина стенки в мм
        thermal_data: Температурные данные
        fire_exposure_time_sec: Время пожара в секундах
        steel_strength_mpa: Прочность стали в МПа
        concrete_strength_mpa: Прочность бетона в МПа
        use_reinforcement: Учитывать ли армирование
        rebar_diameter_mm: Диаметр арматуры в мм
        rebar_count: Количество стержней
        num_rings: Количество бетонных колец
        ring_thicknesses: Толщины колец

    Returns:
        Несущая способность в кН (без учёта гибкости)
    """
    N_total = 0.0

    # Получаем запись температурных данных
    thermal_record = get_thermal_record_for_time(thermal_data, fire_exposure_time_sec)

    # Разбиваем бетонное ядро на кольца
    concrete_rings = discretize_concrete_core_into_rings(
        diameter_mm, thickness_mm, thermal_data, fire_exposure_time_sec,
        num_rings, ring_thicknesses
    )

    # Суммируем несущие способности бетонных колец
    for ring in concrete_rings:
        if ring['area_mm2'] is not None and ring['temperature_celsius'] is not None:
            gamma_bt = concrete_working_condition_coeff(ring['temperature_celsius'])
            f_cd_fire = gamma_bt * concrete_strength_mpa
            area_m2 = ring['area_mm2'] / 1e6
            N_ring = area_m2 * f_cd_fire * 1e3  # кН
            N_total += N_ring

    # Добавляем несущую способность стального кольца
    if thermal_record:
        temp_steel = thermal_record.get('temp_t1')
        if temp_steel is not None and isinstance(temp_steel, (int, float)):
            area_steel_ring = steel_ring_area(diameter_mm, thickness_mm)
            gamma_st = steel_working_condition_coeff(temp_steel)
            f_yd_fire = gamma_st * steel_strength_mpa
            N_steel_ring = area_steel_ring / 1e6 * f_yd_fire * 1e3  # кН
            N_total += N_steel_ring

    # Добавляем несущую способность арматуры
    if use_reinforcement and thermal_record:
        temp_rebar = thermal_record.get('temp_t4')
        if temp_rebar is not None and isinstance(temp_rebar, (int, float)):
            rebar_area = (math.pi * rebar_diameter_mm**2 / 4) * rebar_count  # мм²
            gamma_st_rebar = steel_working_condition_coeff(temp_rebar)
            f_yd_rebar = gamma_st_rebar * steel_strength_mpa
            N_rebar = rebar_area / 1e6 * f_yd_rebar * 1e3  # кН
            N_total += N_rebar

    return N_total


def calculate_final_capacity(
    diameter_mm: float,
    thickness_mm: float,
    height_m: float,
    effective_length_coeff: float,
    thermal_data: List[Dict],
    fire_exposure_time_sec: float,
    steel_strength_mpa: float,
    steel_elastic_modulus_mpa: float,
    concrete_strength_mpa: float,
    use_reinforcement: bool = False,
    rebar_diameter_mm: int = 10,
    rebar_count: int = 8,
    num_rings: int = 7,
    ring_thicknesses: Optional[List[Optional[float]]] = None
) -> Tuple[float, float, float, float]:
    """
    Полный расчёт несущей способности с учётом гибкости.

    Returns:
        Кортеж (N_final, N_total, N_cr, slenderness, reduction_coeff):
        - N_final: Итоговая несущая способность в кН
        - N_total: Несущая способность без учёта гибкости в кН
        - N_cr: Критическая сила в кН
        - slenderness: Условная гибкость
        - reduction_coeff: Понижающий коэффициент
    """
    # Расчёт жёсткости
    total_stiffness = calculate_stiffness_for_time(
        diameter_mm, thickness_mm, thermal_data, fire_exposure_time_sec,
        concrete_strength_mpa, steel_elastic_modulus_mpa,
        use_reinforcement, rebar_diameter_mm, rebar_count,
        num_rings, ring_thicknesses
    )

    # Расчёт несущей способности (без учёта гибкости)
    N_total = calculate_capacity_for_time(
        diameter_mm, thickness_mm, thermal_data, fire_exposure_time_sec,
        steel_strength_mpa, concrete_strength_mpa,
        use_reinforcement, rebar_diameter_mm, rebar_count,
        num_rings, ring_thicknesses
    )

    # Расчёт критической силы
    if total_stiffness > 0 and height_m > 0 and effective_length_coeff > 0:
        N_cr = (math.pi ** 2) * total_stiffness / ((height_m * effective_length_coeff) ** 2)
    else:
        N_cr = 0.0

    # Расчёт условной гибкости
    if N_cr > 0:
        slenderness = math.sqrt(N_total / N_cr)
    else:
        slenderness = 0.0

    # Получение понижающего коэффициента
    reduction_coeff = get_reduction_coeff(slenderness)

    # Итоговая несущая способность
    N_final = N_total * reduction_coeff

    return N_final, N_total, N_cr, slenderness, reduction_coeff


def get_reduction_coeff(slenderness: float) -> float:
    """
    Получить понижающий коэффициент по условной гибкости.

    Линейная интерполяция по таблице нормативных значений.

    Args:
        slenderness: Условная гибкость λ̄

    Returns:
        Понижающий коэффициент φ
    """
    table = [
        (0.0, 1.0),
        (0.2, 1.0),
        (0.4, 0.9),
        (0.6, 0.785),
        (0.8, 0.6),
        (1.0, 0.54),
        (1.2, 0.43),
        (1.4, 0.36),
        (1.6, 0.285),
        (1.8, 0.24),
        (2.0, 0.2),
        (2.2, 0.17),
        (2.4, 0.15),
        (2.6, 0.125),
        (2.8, 0.11),
        (3.0, 0.1),
    ]

    if slenderness <= table[0][0]:
        return table[0][1]
    if slenderness >= table[-1][0]:
        return table[-1][1]

    # Линейная интерполяция
    for i in range(1, len(table)):
        x0, y0 = table[i-1]
        x1, y1 = table[i]
        if x0 <= slenderness <= x1:
            return y0 + (y1 - y0) * (slenderness - x0) / (x1 - x0)

    return table[-1][1]
