import sys
import os
import json
import math
import pandas as pd
import matplotlib.pyplot as plt
import altair as alt
import streamlit as st
import plotly.graph_objects as go
import numpy as np
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.utils import (
    calc_section, calc_capacity, discretize_concrete_core_into_rings,
    steel_ring_area, steel_working_condition_coeff,
    concrete_working_condition_coeff, concrete_strain_by_temp,
    calculate_steel_ring
)
from app.config import (
    GEOMETRY_LIMITS, MATERIAL_CONSTANTS, CALCULATION_CONFIG, DEFAULT_VALUES
)
from app.validation import validate_all_inputs
from app.calculations import (
    calculate_final_capacity, calculate_capacity_for_time,
    calculate_stiffness_for_time, get_reduction_coeff
)

# Функция get_reduction_coeff перенесена в calculations.py

st.set_page_config(page_title="Расчёт огнестойкости сталетрубобетонной колонны", page_icon="🔥", layout="wide")
st.markdown('<div style="text-align:center; font-size:2em; font-weight:700; font-family:Segoe UI, Arial, sans-serif; margin-bottom:0.7em; margin-top:0.2em;">🔥 Расчёт огнестойкости сталетрубобетонной колонны</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Ввод данных")

    with st.expander("📏 Геометрия", expanded=True):
        diameter = st.number_input(
            "Наружный диаметр, мм",
            min_value=GEOMETRY_LIMITS.MIN_DIAMETER_MM,
            max_value=GEOMETRY_LIMITS.MAX_DIAMETER_MM,
            value=DEFAULT_VALUES.DIAMETER_MM,
            step=0.1
        )
        thickness = st.number_input(
            "Толщина стенки, мм",
            min_value=GEOMETRY_LIMITS.MIN_THICKNESS_MM,
            max_value=GEOMETRY_LIMITS.MAX_THICKNESS_MM,
            value=DEFAULT_VALUES.THICKNESS_MM,
            step=0.1
        )
        height = st.number_input(
            "Высота колонны, м",
            min_value=GEOMETRY_LIMITS.MIN_HEIGHT_M,
            max_value=GEOMETRY_LIMITS.MAX_HEIGHT_M,
            value=DEFAULT_VALUES.HEIGHT_M,
            step=0.1
        )
        effective_length_coefficient = st.number_input(
            "Коэфф. расч. длины",
            min_value=0.1,
            max_value=5.0,
            value=DEFAULT_VALUES.EFFECTIVE_LENGTH_COEFF,
            step=0.1
        )

    with st.expander("🧱 Материалы", expanded=True):
        steel_strength_normative = st.number_input(
            "Ryn стали, МПа",
            min_value=200,
            max_value=1000,
            value=DEFAULT_VALUES.STEEL_STRENGTH_MPA
        )
        steel_elastic_modulus = st.number_input(
            "E стали, МПа",
            min_value=150000,
            max_value=250000,
            value=DEFAULT_VALUES.STEEL_ELASTIC_MODULUS_MPA
        )
        concrete_strength_normative = st.number_input(
            "Rbn бетона, МПа",
            min_value=5.0,
            max_value=120.0,
            value=DEFAULT_VALUES.CONCRETE_STRENGTH_MPA,
            step=0.1
        )

    with st.expander("🔥 Нагрузка и Огонь", expanded=True):
        normative_load = st.number_input(
            "Нагрузка, кН",
            min_value=0.0,
            max_value=50000.0,
            value=DEFAULT_VALUES.NORMATIVE_LOAD_KN,
            step=10.0
        )
        fire_exposure_time = st.number_input(
            "Время пожара, мин",
            min_value=0,
            max_value=360,
            value=DEFAULT_VALUES.FIRE_EXPOSURE_TIME_MIN,
            step=5
        )

    with st.expander("🏗️ Армирование"):
        use_reinforcement = st.checkbox("Учитывать армирование", value=True)
        rebar_count = st.number_input(
            "Кол-во стержней",
            min_value=0,
            max_value=40,
            value=MATERIAL_CONSTANTS.DEFAULT_REBAR_COUNT,
            step=1
        )
        rebar_diameter = st.number_input(
            "Диаметр стержня, мм",
            min_value=4,
            max_value=60,
            value=MATERIAL_CONSTANTS.DEFAULT_REBAR_DIAMETER_MM,
            step=1
        )
        rebar_strength_normative = st.number_input(
            "Ryn арматуры, МПа",
            min_value=200,
            max_value=1000,
            value=DEFAULT_VALUES.REBAR_STRENGTH_MPA,
            help="Нормативное сопротивление стали арматуры. По умолчанию равно сопротивлению стали оболочки."
        )

# === ВАЛИДАЦИЯ ВХОДНЫХ ДАННЫХ ===
is_valid, error_message = validate_all_inputs(
    diameter, thickness, height,
    steel_strength_normative, steel_elastic_modulus, concrete_strength_normative,
    normative_load, fire_exposure_time,
    use_reinforcement, rebar_count, rebar_diameter
)

if not is_valid:
    st.error(error_message)
    st.stop()  # Останавливаем выполнение при некорректных данных

@st.cache_data(show_spinner="Загрузка температурных данных...")
def load_thermal_data():
    """
    Загрузка температурных данных из JSON файлов с кэшированием.

    Returns:
        Словарь {(диаметр, толщина): данные}
    """
    thermal_dir = Path(PROJECT_ROOT) / "thermal_data"
    if not thermal_dir.exists():
        st.error(f"❌ Директория {thermal_dir} не найдена!")
        return {}

    thermal_files = list(thermal_dir.glob("*.json"))
    if not thermal_files:
        st.error(f"❌ JSON файлы не найдены в директории {thermal_dir}!")
        return {}

    thermal_data = {}
    for file in thermal_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            name = file.stem
            # Нормализация: замена кириллического 'х' на латинский 'x'
            name_clean = name.replace('х', 'x').replace('Х', 'x')

            try:
                if 'x' in name_clean:
                    parts = name_clean.split('x')
                elif ',' in name_clean:
                    parts = name_clean.split(',')
                else:
                    parts = [name_clean]

                if len(parts) >= 2:
                    diameter_val = float(parts[0].replace(',', '.'))
                    thickness_val = float(parts[1].replace(',', '.'))
                    thermal_data[(diameter_val, thickness_val)] = data
                else:
                    st.warning(f"⚠️ Не удалось определить диаметр и толщину из имени файла: {file.name}")
            except ValueError:
                st.warning(f"⚠️ Ошибка при разборе имени файла: {file.name}")
                continue
        except Exception as e:
            st.error(f"❌ Ошибка при загрузке файла {file.name}: {str(e)}")

    return thermal_data

def get_closest_thermal_data(thermal_data, diameter, thickness):
    if not thermal_data:
        st.error("Нет доступных температурных данных!")
        return None
        
    available_diameters = sorted(set(d for d, _ in thermal_data.keys()))
    available_thicknesses = sorted(set(t for _, t in thermal_data.keys()))
    
    if not available_diameters or not available_thicknesses:
        st.error("Нет доступных размеров в температурных данных!")
        return None
    
    closest_diameter = min(available_diameters, key=lambda d: abs(d - diameter))
    closest_thickness = min(available_thicknesses, key=lambda t: abs(t - thickness))
    
    st.info(f"Температурные данные приняты для диаметра {closest_diameter} мм и толщины {closest_thickness} мм")
    
    return thermal_data.get((closest_diameter, closest_thickness), None)

thermal_data = load_thermal_data()
closest_data = get_closest_thermal_data(thermal_data, diameter, thickness)

if closest_data:
    st.toast(f"Загружены данные для диаметра {diameter} мм и толщины {thickness} мм", icon="✅")
else:
    st.toast("Данные не найдены", icon="❌")

# Расчет и отображение разбиения бетонного ядра на кольца
fire_exposure_time_sec = fire_exposure_time * 60
concrete_rings_details = discretize_concrete_core_into_rings(
    diameter, 
    thickness, 
    closest_data, 
    fire_exposure_time_sec,
    num_rings=7,  # Устанавливаем 7 колец
    ring_thicknesses=[10, 20, 20, 20, 20, 20, None]  # Задаем толщины колец, последнее кольцо займет оставшееся пространство
)
temp_steel = None
temp_rebar = None
if closest_data:
    suitable_records = [r for r in closest_data if isinstance(r.get('time_minutes'), (int, float)) and r.get('time_minutes', -1) <= fire_exposure_time_sec]
    if suitable_records:
        thermal_record = max(suitable_records, key=lambda x: x.get('time_minutes', -1))
    else:
        all_time_records = [r for r in closest_data if isinstance(r.get('time_minutes'), (int, float))]
        if all_time_records:
            thermal_record = min(all_time_records, key=lambda x: x.get('time_minutes', float('inf')))
        else:
            thermal_record = None
    if thermal_record:
        temp_steel = thermal_record.get('temp_t1')  # Температура стального кольца
        temp_rebar = thermal_record.get('temp_t4')  # Температура арматуры

# Инициализируем переменные для сводной таблицы перед их вычислением
N_cr_for_summary_table = None
slenderness_for_summary_table = None
reduction_coeff_for_summary_table = None
N_final_for_summary_table = None

# Суммируем жёсткости всех колец (бетонных и стального) для выбранного fire_exposure_time
total_stiffness = 0.0
if concrete_rings_details:
    for ring in concrete_rings_details:
        R_out = ring['outer_radius_mm']
        R_in = ring['inner_radius_mm']
        I_ring = (math.pi / 4) * (R_out**4 - R_in**4) / 1e12  # м^4
        if ring['temperature_celsius'] is not None:
            gamma_bt = concrete_working_condition_coeff(ring['temperature_celsius'])
            f_cd_fire = gamma_bt * concrete_strength_normative
            strain = concrete_strain_by_temp(ring['temperature_celsius'])
            if strain and strain > 0:
                E_c_fire = f_cd_fire / (strain * 1e-3)
                total_stiffness += I_ring * E_c_fire * 1e3  # кН·м²

# Добавляем жёсткость стального кольца
if temp_steel is not None and isinstance(temp_steel, (int, float)):
    gamma_st = steel_working_condition_coeff(temp_steel)
    E_steel_fire = steel_elastic_modulus * gamma_st
    R_out_steel = diameter / 2
    R_in_steel = R_out_steel - thickness
    I_steel_ring = (math.pi / 4) * (R_out_steel**4 - R_in_steel**4) / 1e12  # м^4
    total_stiffness += I_steel_ring * E_steel_fire * 1e3  # кН·м²

# Добавляем жёсткость арматуры
if use_reinforcement:
    if temp_rebar is not None and isinstance(temp_rebar, (int, float)):
        gamma_st_rebar = steel_working_condition_coeff(temp_rebar)
        E_rebar_fire = steel_elastic_modulus * gamma_st_rebar
        rebar_distance_mm = (diameter / 2) - thickness - 35 - (rebar_diameter / 2)  # расстояние от центра до арматуры (защитный слой 35 мм)
        I_self_bar = (math.pi * rebar_diameter**4) / 64  # момент инерции одного стержня
        rebar_area_one = (math.pi * rebar_diameter**2) / 4 # площадь одного стержня
        # Формула: 8 * I_s + 4 * A_s * (R - a)^2
        # rebar_distance_mm - это (R - a)
        I_rebar = (8 * I_self_bar + 4 * rebar_area_one * rebar_distance_mm**2) * 1e-12  # м^4
        total_stiffness += I_rebar * E_rebar_fire * 1e3  # кН·м²

# Критическая сила для выбранного fire_exposure_time
if total_stiffness > 0 and height > 0 and effective_length_coefficient > 0:
    N_cr_for_summary_table = (math.pi ** 2) * total_stiffness / ((height * effective_length_coefficient) ** 2)

# Суммируем несущие способности всех колец для выбранного fire_exposure_time
N_total = 0.0
if concrete_rings_details:
    for ring in concrete_rings_details:
        if ring['area_mm2'] is not None and ring['temperature_celsius'] is not None:
            gamma_bt = concrete_working_condition_coeff(ring['temperature_celsius'])
            f_cd_fire = gamma_bt * concrete_strength_normative
            area_m2 = ring['area_mm2'] / 1e6
            N_ring = area_m2 * f_cd_fire * 1e3  # кН
            N_total += N_ring

# Добавляем несущую способность стального кольца
if temp_steel is not None and isinstance(temp_steel, (int, float)):
    area_steel_ring = steel_ring_area(diameter, thickness)
    gamma_st = steel_working_condition_coeff(temp_steel)
    f_yd_fire = gamma_st * steel_strength_normative
    N_steel_ring = area_steel_ring / 1e6 * f_yd_fire * 1e3
    N_total += N_steel_ring

# Добавляем несущую способность арматуры
if use_reinforcement:
    if temp_rebar is not None and isinstance(temp_rebar, (int, float)):
        rebar_area = (math.pi * rebar_diameter**2 / 4) * rebar_count  # мм²
        gamma_st_rebar = steel_working_condition_coeff(temp_rebar)
        f_yd_rebar = gamma_st_rebar * rebar_strength_normative
        N_rebar = rebar_area / 1e6 * f_yd_rebar * 1e3
        N_total += N_rebar

# Условная гибкость и итоговая несущая способность для выбранного fire_exposure_time
if N_cr_for_summary_table is not None and N_cr_for_summary_table > 0:
    slenderness_for_summary_table = math.sqrt(N_total / N_cr_for_summary_table)
    reduction_coeff_for_summary_table = get_reduction_coeff(slenderness_for_summary_table)
    N_final_for_summary_table = N_total * reduction_coeff_for_summary_table

# График несущей способности колонны от времени
if closest_data:
    times = sorted(set(int(r['time_minutes'])//60 for r in closest_data if isinstance(r.get('time_minutes'), (int, float))))
    times = [t for t in range(0, max(times)+1)] if times else [0]
    N_final_list = []
    for t_min in times:
        t_sec = t_min * 60
        # Получаем thermal_record для этого времени
        suitable_records = [r for r in closest_data if isinstance(r.get('time_minutes'), (int, float)) and r.get('time_minutes', -1) <= t_sec]
        if suitable_records:
            thermal_record = max(suitable_records, key=lambda x: x.get('time_minutes', -1))
        else:
            all_time_records = [r for r in closest_data if isinstance(r.get('time_minutes'), (int, float))]
            if all_time_records:
                thermal_record = min(all_time_records, key=lambda x: x.get('time_minutes', float('inf')))
            else:
                thermal_record = None
        # Пересчёт для каждого времени
        # Бетонные кольца
        N_total = 0.0
        total_stiffness = 0.0
        for i in range(7):  # 7 бетонных колец
            # Радиусы
            column_radius_mm = diameter / 2.0
            concrete_core_outer_radius_mm = column_radius_mm - thickness
            nominal_thicknesses_mm = [10.0, 20.0, 20.0, 20.0, 20.0, 20.0, None]  # 7 колец
            if i < 6:  # Для первых 6 колец
                outer_r = concrete_core_outer_radius_mm - sum(t for t in nominal_thicknesses_mm[:i] if t is not None)
                inner_r = max(0.0, outer_r - (nominal_thicknesses_mm[i] if nominal_thicknesses_mm[i] is not None else outer_r))
            else:  # Для последнего кольца
                outer_r = concrete_core_outer_radius_mm - sum(t for t in nominal_thicknesses_mm[:i] if t is not None)
                inner_r = 0.0
            area = math.pi * (outer_r**2 - inner_r**2) if outer_r > inner_r else 0.0
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
            gamma_bt = concrete_working_condition_coeff(temp) if temp is not None else None
            f_cd_fire = gamma_bt * concrete_strength_normative if gamma_bt is not None else None
            strain = concrete_strain_by_temp(temp) if temp is not None else None
            E_c_fire = f_cd_fire / (strain * 1e-3) if (f_cd_fire is not None and strain and strain > 0) else None
            I_ring = (math.pi / 4) * (outer_r**4 - inner_r**4) / 1e12 if outer_r > inner_r else 0.0
            N_ring = area / 1e6 * f_cd_fire * 1e3 if (area > 0 and f_cd_fire is not None) else 0.0
            stiffness = I_ring * E_c_fire * 1e3 if (I_ring and E_c_fire) else 0.0
            N_total += N_ring
            total_stiffness += stiffness
        # Стальное кольцо
        temp_steel = thermal_record.get('temp_t1') if thermal_record else None
        gamma_st = steel_working_condition_coeff(temp_steel) if temp_steel is not None else None
        f_yd_fire = gamma_st * steel_strength_normative if gamma_st is not None else None
        E_steel_fire = steel_elastic_modulus * gamma_st if gamma_st is not None else None
        R_out_steel = diameter / 2
        R_in_steel = R_out_steel - thickness
        I_steel_ring = (math.pi / 4) * (R_out_steel**4 - R_in_steel**4) / 1e12
        area_steel_ring = steel_ring_area(diameter, thickness)
        N_steel_ring = area_steel_ring / 1e6 * f_yd_fire * 1e3 if (f_yd_fire is not None) else 0.0
        stiffness_steel = I_steel_ring * E_steel_fire * 1e3 if (E_steel_fire is not None) else 0.0
        N_total += N_steel_ring
        total_stiffness += stiffness_steel

        # Арматура (добавлено в цикле)
        if use_reinforcement:
            temp_rebar = thermal_record.get('temp_t4') if thermal_record else None
            if temp_rebar is not None:
                 gamma_st_rebar = steel_working_condition_coeff(temp_rebar)
                 f_yd_rebar = gamma_st_rebar * rebar_strength_normative
                 E_rebar_fire = steel_elastic_modulus * gamma_st_rebar
                 
                 # Несущая способность арматуры
                 rebar_area = (math.pi * rebar_diameter**2 / 4) * rebar_count
                 N_rebar = rebar_area / 1e6 * f_yd_rebar * 1e3
                 N_total += N_rebar

                 # Жесткость арматуры (Новая формула)
                 rebar_distance_mm = (diameter / 2) - thickness - 35 - (rebar_diameter / 2)
                 I_self_bar = (math.pi * rebar_diameter**4) / 64
                 rebar_area_one = (math.pi * rebar_diameter**2) / 4
                 # Формула: 8 * I_s + 4 * A_s * (R - a)^2
                 I_rebar = (8 * I_self_bar + 4 * rebar_area_one * rebar_distance_mm**2) * 1e-12
                 
                 stiffness_rebar = I_rebar * E_rebar_fire * 1e3
                 total_stiffness += stiffness_rebar

        # Критическая сила
        N_cr = (math.pi ** 2) * total_stiffness / ((height * effective_length_coefficient) ** 2) if (total_stiffness > 0 and height > 0 and effective_length_coefficient > 0) else 0.0
        # Условная гибкость
        slenderness = math.sqrt(N_total / N_cr) if N_cr > 0 else 0.0
        reduction_coeff = get_reduction_coeff(slenderness)
        N_final = N_total * reduction_coeff
        N_final_list.append(N_final)

    # Коэффициент запаса прочности n = N_final / normative_load
    if normative_load > 0:
        n_safety_list = [N / normative_load for N in N_final_list]
    else:
        n_safety_list = [0] * len(N_final_list)

# --- Формирование table_data_list с едиными ключами ---
table_data_list = []
# Данные по бетонным кольцам
if concrete_rings_details:
    for i, ring_detail in enumerate(concrete_rings_details):
        R_out_mm_c = ring_detail['outer_radius_mm']
        R_in_mm_c = ring_detail['inner_radius_mm']
        area_mm2_c = ring_detail['area_mm2']
        temp_c_c = ring_detail['temperature_celsius']
        gamma_bt_c = None
        f_cd_fire_mpa_c = None
        strain_c_permille = None
        E_c_fire_mpa_c = None
        N_ring_kn_c = None
        I_ring_m4_c = (math.pi / 4) * (R_out_mm_c**4 - R_in_mm_c**4) / 1e12 if R_out_mm_c > R_in_mm_c else 0.0
        stiffness_ring_knm2_c = None
        if temp_c_c is not None:
            gamma_bt_c = concrete_working_condition_coeff(temp_c_c)
            if gamma_bt_c is not None:
                f_cd_fire_mpa_c = gamma_bt_c * concrete_strength_normative
            strain_c_permille = concrete_strain_by_temp(temp_c_c)
            if strain_c_permille is not None and strain_c_permille > 0 and f_cd_fire_mpa_c is not None:
                E_c_fire_mpa_c = f_cd_fire_mpa_c / (strain_c_permille / 1000)
        if area_mm2_c is not None and f_cd_fire_mpa_c is not None:
            N_ring_kn_c = (area_mm2_c / 1e6) * f_cd_fire_mpa_c * 1e3
        if I_ring_m4_c != 0 and E_c_fire_mpa_c is not None:
            stiffness_ring_knm2_c = I_ring_m4_c * E_c_fire_mpa_c * 1e3
        table_data_list.append({
            "№": f"Б{i+1}",
            "Наружный радиус, R<sub>нар</sub>, мм": f"{R_out_mm_c:.1f}",
            "Внутренний радиус, R<sub>вн</sub>, мм": f"{R_in_mm_c:.1f}",
            "Площадь сечения, A, мм²": f"{area_mm2_c:.1f}" if area_mm2_c is not None else "N/A",
            "Температура, T, °C": f"{temp_c_c:.1f}" if temp_c_c is not None else "N/A",
            "Коэффициент условий работы бетона, γ<sub>bt</sub>": f"{gamma_bt_c:.3f}" if gamma_bt_c is not None else "N/A",
            "Расчётное сопротивление бетона, R<sub>bu</sub>, МПа": f"{f_cd_fire_mpa_c:.1f}" if f_cd_fire_mpa_c is not None else "N/A",
            "Деформация бетона, ε<sub>yn,t</sub>": f"{strain_c_permille:.2f}" if strain_c_permille is not None else "N/A",
            "Модуль деформации бетона, E<sub>b,t</sub>, МПа": f"{E_c_fire_mpa_c:.0f}" if E_c_fire_mpa_c is not None else "N/A",
            "Момент инерции, I, м⁴": f"{I_ring_m4_c:.2e}",
            "Несущая способность кольца, N<sub>p,t</sub>, кН": f"{N_ring_kn_c:.1f}" if N_ring_kn_c is not None else "N/A",
            "Жёсткость кольца, EI, кН·м²": f"{stiffness_ring_knm2_c:.1f}" if stiffness_ring_knm2_c is not None else "N/A",
        })
# Данные по стальному кольцу и арматуре
s_temp_steel = None
s_temp_rebar = None
if closest_data:
    suitable_records = [r for r in closest_data if isinstance(r.get('time_minutes'), (int, float)) and r.get('time_minutes', -1) <= fire_exposure_time_sec]
    if suitable_records:
        s_thermal_record = max(suitable_records, key=lambda x: x.get('time_minutes', -1))
    else:
        all_time_records = [r for r in closest_data if isinstance(r.get('time_minutes'), (int, float))]
        if all_time_records:
            s_thermal_record = min(all_time_records, key=lambda x: x.get('time_minutes', float('inf')))
        else:
            s_thermal_record = None
    if s_thermal_record:
        s_temp_steel = s_thermal_record.get('temp_t1')
        s_temp_rebar = s_thermal_record.get('temp_t4')

s_gamma_st = None
s_f_yd_fire_mpa = None
s_E_steel_fire_mpa = None
s_N_steel_ring_kn = None
s_stiffness_steel_knm2 = None
s_area_mm2 = steel_ring_area(diameter, thickness)
s_R_out_mm = diameter / 2.0
s_R_in_mm = s_R_out_mm - thickness
s_I_steel_ring_m4 = (math.pi / 4) * (s_R_out_mm**4 - s_R_in_mm**4) / 1e12

if s_temp_steel is not None and isinstance(s_temp_steel, (int, float)):
    s_gamma_st = steel_working_condition_coeff(s_temp_steel)
    if s_gamma_st is not None:
        s_f_yd_fire_mpa = s_gamma_st * steel_strength_normative
        s_E_steel_fire_mpa = steel_elastic_modulus * s_gamma_st
if s_area_mm2 is not None and s_f_yd_fire_mpa is not None:
    s_N_steel_ring_kn = (s_area_mm2 / 1e6) * s_f_yd_fire_mpa * 1e3
if s_I_steel_ring_m4 != 0 and s_E_steel_fire_mpa is not None:
    s_stiffness_steel_knm2 = s_I_steel_ring_m4 * s_E_steel_fire_mpa * 1e3

# Данные по арматуре
s_gamma_st_rebar = None
s_f_yd_rebar_mpa = None
s_E_rebar_fire_mpa = None
s_N_rebar_kn = None
s_stiffness_rebar_knm2 = None
s_rebar_area_mm2 = (math.pi * rebar_diameter**2 / 4) * rebar_count
s_rebar_radius = (diameter / 2) - thickness - 35 - (rebar_diameter / 2)
rebar_distance_mm = s_rebar_radius  # расстояние от центра до арматуры
s_I_self_bar = (math.pi * rebar_diameter**4) / 64
s_rebar_area_one = (math.pi * rebar_diameter**2) / 4
s_I_rebar_m4 = (8 * s_I_self_bar + 4 * s_rebar_area_one * rebar_distance_mm**2) * 1e-12  # м^4

if s_temp_rebar is not None and isinstance(s_temp_rebar, (int, float)):
    s_gamma_st_rebar = steel_working_condition_coeff(s_temp_rebar)
    if s_gamma_st_rebar is not None:
        s_f_yd_rebar_mpa = s_gamma_st_rebar * rebar_strength_normative
        s_E_rebar_fire_mpa = steel_elastic_modulus * s_gamma_st_rebar
if s_rebar_area_mm2 is not None and s_f_yd_rebar_mpa is not None:
    s_N_rebar_kn = (s_rebar_area_mm2 / 1e6) * s_f_yd_rebar_mpa * 1e3
if s_I_rebar_m4 != 0 and s_E_rebar_fire_mpa is not None:
    s_stiffness_rebar_knm2 = s_I_rebar_m4 * s_E_rebar_fire_mpa * 1e3

table_data_list.append({
    "№": "Ст",
    "Наружный радиус, R<sub>нар</sub>, мм": f"{s_R_out_mm:.1f}",
    "Внутренний радиус, R<sub>вн</sub>, мм": f"{s_R_in_mm:.1f}",
    "Площадь сечения, A, мм²": f"{s_area_mm2:.1f}" if s_area_mm2 is not None else "N/A",
    "Температура, T, °C": f"{s_temp_steel:.1f}" if s_temp_steel is not None else "N/A",
    "Коэффициент условий работы стали, γ<sub>st</sub>": f"{s_gamma_st:.3f}" if s_gamma_st is not None else "N/A",
    "Расчётное сопротивление стали, R<sub>su</sub>, МПа": f"{s_f_yd_fire_mpa:.1f}" if s_f_yd_fire_mpa is not None else "N/A",
    "Модуль упругости стали, E<sub>s,t</sub>, МПа": f"{s_E_steel_fire_mpa:.0f}" if s_E_steel_fire_mpa is not None else "N/A",
    "Момент инерции, I, м⁴": f"{s_I_steel_ring_m4:.2e}",
    "Несущая способность кольца, N<sub>p,t</sub>, кН": f"{s_N_steel_ring_kn:.1f}" if s_N_steel_ring_kn is not None else "N/A",
    "Жёсткость кольца, EI, кН·м²": f"{s_stiffness_steel_knm2:.1f}" if s_stiffness_steel_knm2 is not None else "N/A",
})

# Добавляем строку с арматурой
if use_reinforcement:
    table_data_list.append({
        "№": "Арм",
        "Наружный радиус, R<sub>нар</sub>, мм": f"{s_rebar_radius:.1f}",
        "Внутренний радиус, R<sub>вн</sub>, мм": f"{s_rebar_radius:.1f}",
        "Площадь сечения, A, мм²": f"{s_rebar_area_mm2:.1f}" if s_rebar_area_mm2 is not None else "N/A",
        "Температура, T, °C": f"{s_temp_rebar:.1f}" if s_temp_rebar is not None else "N/A",
        "Коэффициент условий работы стали, γ<sub>st</sub>": f"{s_gamma_st_rebar:.3f}" if s_gamma_st_rebar is not None else "N/A",
        "Расчётное сопротивление стали, R<sub>su</sub>, МПа": f"{s_f_yd_rebar_mpa:.1f}" if s_f_yd_rebar_mpa is not None else "N/A",
        "Модуль упругости стали, E<sub>s,t</sub>, МПа": f"{s_E_rebar_fire_mpa:.0f}" if s_E_rebar_fire_mpa is not None else "N/A",
        "Момент инерции, I, м⁴": f"{s_I_rebar_m4:.2e}",
        "Несущая способность кольца, N<sub>p,t</sub>, кН": f"{s_N_rebar_kn:.1f}" if s_N_rebar_kn is not None else "N/A",
        "Жёсткость кольца, EI, кН·м²": f"{s_stiffness_rebar_knm2:.1f}" if s_stiffness_rebar_knm2 is not None else "N/A",
    })

# --- Единые списки столбцов ---
concrete_columns = [
    "№",
    "Наружный радиус, R<sub>нар</sub>, мм",
    "Внутренний радиус, R<sub>вн</sub>, мм",
    "Площадь сечения, A, мм²",
    "Температура, T, °C",
    "Коэффициент условий работы бетона, γ<sub>bt</sub>",
    "Расчётное сопротивление бетона, R<sub>bu</sub>, МПа",
    "Деформация бетона, ε<sub>yn,t</sub>",
    "Модуль деформации бетона, E<sub>b,t</sub>, МПа",
    "Момент инерции, I, м⁴",
    "Несущая способность кольца, N<sub>p,t</sub>, кН",
    "Жёсткость кольца, EI, кН·м²",
]
steel_columns = [
    "№",
    "Наружный радиус, R<sub>нар</sub>, мм",
    "Внутренний радиус, R<sub>вн</sub>, мм",
    "Площадь сечения, A, мм²",
    "Температура, T, °C",
    "Коэффициент условий работы стали, γ<sub>st</sub>",
    "Расчётное сопротивление стали, R<sub>su</sub>, МПа",
    "Модуль упругости стали, E<sub>s,t</sub>, МПа",
    "Момент инерции, I, м⁴",
    "Несущая способность кольца, N<sub>p,t</sub>, кН",
    "Жёсткость кольца, EI, кН·м²",
]
# --- header_map с полными названиями показателей и переносами строк ---
header_map = {
    "№": ("Номер<br>кольца", ""),
    "Наружный радиус, R<sub>нар</sub>, мм": ("Наружный<br>радиус", "R<sub>нар</sub>, мм"),
    "Внутренний радиус, R<sub>вн</sub>, мм": ("Внутренний<br>радиус", "R<sub>вн</sub>, мм"),
    "Площадь сечения, A, мм²": ("Площадь<br>сечения", "A, мм²"),
    "Температура, T, °C": ("Температура", "T, °C"),
    "Коэффициент условий работы бетона, γ<sub>bt</sub>": ("Коэффициент<br>условий работы<br>бетона", "γ<sub>bt</sub>"),
    "Расчётное сопротивление бетона, R<sub>bu</sub>, МПа": ("Расчётное<br>сопротивление<br>бетона", "R<sub>bu</sub>, МПа"),
    "Деформация бетона, ε<sub>yn,t</sub>": ("Деформация<br>бетона", "ε<sub>yn,t</sub>"),
    "Модуль деформации бетона, E<sub>b,t</sub>, МПа": ("Модуль<br>деформации<br>бетона", "E<sub>b,t</sub>, МПа"),
    "Коэффициент условий работы стали, γ<sub>st</sub>": ("Коэффициент<br>условий работы<br>стали", "γ<sub>st</sub>"),
    "Расчётное сопротивление стали, R<sub>su</sub>, МПа": ("Расчётное<br>сопротивление<br>стали", "R<sub>su</sub>, МПа"),
    "Модуль упругости стали, E<sub>s,t</sub>, МПа": ("Модуль<br>упругости<br>стали", "E<sub>s,t</sub>, МПа"),
    "Момент инерции, I, м⁴": ("Момент<br>инерции", "I, м⁴"),
    "Несущая способность кольца, N<sub>p,t</sub>, кН": ("Несущая<br>способность<br>кольца", "N<sub>p,t</sub>, кН"),
    "Жёсткость кольца, EI, кН·м²": ("Жёсткость<br>кольца", "EI, кН·м²"),
}

df = pd.DataFrame(table_data_list)
# Теперь переменная df создана и содержит все данные для таблицы
# Она будет использована в первой вкладке: st.dataframe(df, ...)

# --- UI: Вкладки и современный дизайн ---
# --- Метрики (Dashboard) ---
# Отображаем метрики ДО вкладок, чтобы они были всегда видны
col_m1, col_m2, col_m3, col_m4 = st.columns(4)

with col_m1:
    if N_final_for_summary_table is not None:
        delta_color = "normal"
        if N_final_for_summary_table < normative_load:
            delta_color = "inverse" # Красный, если сломалось
        st.metric("Несущая способность", f"{N_final_for_summary_table:.0f} кН", f"{N_final_for_summary_table - normative_load:.0f} кН запас", delta_color=delta_color)
    else:
         st.metric("Несущая способность", "N/A")

with col_m2:
     st.metric("Действующая нагрузка", f"{normative_load:.0f} кН")

with col_m3:
    if total_stiffness is not None and total_stiffness > 0:
        st.metric("Жесткость (EI)", f"{total_stiffness/1000:.1f} МН·м²") # В МН для краткости
    else:
        st.metric("Жесткость (EI)", "N/A")

with col_m4:
    if N_final_for_summary_table and N_final_for_summary_table > 0:
        util = normative_load / N_final_for_summary_table
        st.metric("Коэфф. использования", f"{util:.2f}")
    else:
        st.metric("Коэфф. использования", "N/A")

st.divider()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🧮 Детальный расчёт",
    "📈 График (N)",
    "📊 Запас прочности",
    "🌡️ График (T)",
    "📐 Сечение",
    "ℹ️ О проекте"
])

with tab1:
    # --- Центрированный и одинаковый стиль заголовков ---
    table_title_style = 'style="text-align:center; font-size:1.25em; font-weight:700; font-family:Segoe UI, Arial, sans-serif; margin-bottom:0.5em; margin-top:0.5em;"'
    if 'df' in locals() and not df.empty:
        df_concrete = df[df['№'] != 'Ст'].copy()
        df_steel = df[df['№'] == 'Ст'].copy()
        # --- Меняем порядок столбцов: наружный, потом внутренний ---
        concrete_columns = [
            "№",
            "Наружный радиус, R<sub>нар</sub>, мм",
            "Внутренний радиус, R<sub>вн</sub>, мм",
            "Площадь сечения, A, мм²",
            "Температура, T, °C",
            "Коэффициент условий работы бетона, γ<sub>bt</sub>",
            "Расчётное сопротивление бетона, R<sub>bu</sub>, МПа",
            "Деформация бетона, ε<sub>yn,t</sub>",
            "Модуль деформации бетона, E<sub>b,t</sub>, МПа",
            "Момент инерции, I, м⁴",
            "Несущая способность кольца, N<sub>p,t</sub>, кН",
            "Жёсткость кольца, EI, кН·м²",
        ]
        steel_columns = [
            "№",
            "Наружный радиус, R<sub>нар</sub>, мм",
            "Внутренний радиус, R<sub>вн</sub>, мм",
            "Площадь сечения, A, мм²",
            "Температура, T, °C",
            "Коэффициент условий работы стали, γ<sub>st</sub>",
            "Расчётное сопротивление стали, R<sub>su</sub>, МПа",
            "Модуль упругости стали, E<sub>s,t</sub>, МПа",
            "Момент инерции, I, м⁴",
            "Несущая способность кольца, N<sub>p,t</sub>, кН",
            "Жёсткость кольца, EI, кН·м²",
        ]
        df_concrete = df_concrete[[col for col in concrete_columns if col in df_concrete.columns]]
        df_steel = df_steel[[col for col in steel_columns if col in df_steel.columns]]
        # ---
        # Маппинг для подписей столбцов (вернул header_map)
        header_map = {
            "№": ("№<br>кольца", ""),
            "Наружный радиус, R<sub>нар</sub>, мм": ("Наружный<br>радиус", "R<sub>нар</sub>, мм"),
            "Внутренний радиус, R<sub>вн</sub>, мм": ("Внутренний<br>радиус", "R<sub>вн</sub>, мм"),
            "Площадь сечения, A, мм²": ("Площадь<br>сечения", "A, мм²"),
            "Температура, T, °C": ("Температура", "T, °C"),
            "Коэффициент условий работы бетона, γ<sub>bt</sub>": ("Коэффициент<br>условий работы<br>бетона", "γ<sub>bt</sub>"),
            "Расчётное сопротивление бетона, R<sub>bu</sub>, МПа": ("Расчётное<br>сопротивление<br>бетона", "R<sub>bu</sub>, МПа"),
            "Деформация бетона, ε<sub>yn,t</sub>": ("Деформация<br>бетона", "ε<sub>yn,t</sub>"),
            "Модуль деформации бетона, E<sub>b,t</sub>, МПа": ("Модуль<br>деформации<br>бетона", "E<sub>b,t</sub>, МПа"),
            "Коэффициент условий работы стали, γ<sub>st</sub>": ("Коэффициент<br>условий работы<br>стали", "γ<sub>st</sub>"),
            "Расчётное сопротивление стали, R<sub>su</sub>, МПа": ("Расчётное<br>сопротивление<br>стали", "R<sub>su</sub>, МПа"),
            "Модуль упругости стали, E<sub>s,t</sub>, МПа": ("Модуль<br>упругости<br>стали", "E<sub>s,t</sub>, МПа"),
            "Момент инерции, I, м⁴": ("Момент<br>инерции", "I, м⁴"),
            "Несущая способность кольца, N<sub>p,t</sub>, кН": ("Несущая<br>способность<br>кольца", "N<sub>p,t</sub>, кН"),
            "Жёсткость кольца, EI, кН·м²": ("Жёсткость<br>кольца", "EI, кН·м²"),
        }
        # Заголовок для бетонных колец
        st.markdown(f'<div {table_title_style}>Расчёт бетонного сечения</div>', unsafe_allow_html=True)
        # Основная таблица (бетонные кольца)
        html = '''
        <style>
        .rings-table-wrapper { overflow-x: auto; }
        .rings-table {
            min-width: 900px;
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 1px 6px 0 rgba(0,0,0,0.04);
            border: 1px solid #e0e0e0;
            font-size: 0.88em;
            table-layout: fixed;
        }
        .rings-table th {
            background: #f6f8fa;
            color: #222;
            font-weight: 600;
            padding: 10px 12px;
            border-bottom: 1.5px solid #eaecef;
            border-right: 1px solid #e0e0e0;
            white-space: normal;
            word-wrap: break-word;
        }
        .rings-table td {
            padding: 8px 12px;
            border-bottom: 1px solid #f0f0f0;
            color: #222;
            border-right: 1px solid #e0e0e0;
            text-align: center;
            white-space: normal;
            word-wrap: break-word;
        }
        .rings-table th:first-child,
        .rings-table td:first-child {
            width: 75px;
        }
        </style>
        <div class="rings-table-wrapper">
        <table class="rings-table">
        <tr>
        '''
        # Фильтруем только строки, начинающиеся с "Б"
        df_concrete_filtered = df[df['№'].str.startswith('Б')].copy()
        
        # Удаляем столбцы, характеризующие сталь
        columns_to_drop = [
            'Коэффициент условий работы стали, γ<sub>st</sub>',
            'Расчётное сопротивление стали, R<sub>su</sub>, МПа',
            'Модуль упругости стали, E<sub>s,t</sub>, МПа'
        ]
        df_concrete_filtered = df_concrete_filtered.drop(columns=columns_to_drop, errors='ignore')
        
        # Перемещаем столбец "Несущая способность кольца" в конец
        columns_order = [col for col in df_concrete_filtered.columns if col != 'Несущая способность кольца, N<sub>p,t</sub>, кН']
        columns_order.append('Несущая способность кольца, N<sub>p,t</sub>, кН')
        df_concrete_filtered = df_concrete_filtered[columns_order]
        
        for col in df_concrete_filtered.columns:
            top, bottom = header_map.get(col, (col, ""))
            html += f'<th style="vertical-align:middle; padding-bottom:2px; text-align:center;">'
            html += f'<div style="font-weight:600; text-align:center; vertical-align:middle;">{top}</div>'
            if bottom:
                html += f'<div style="font-size:0.92em; color:#888; font-weight:400; text-align:center; vertical-align:middle;">{bottom}</div>'
            html += '</th>'
        html += '</tr>'
        for _, row in df_concrete_filtered.iterrows():
            html += '<tr>'
            for val in row:
                html += f'<td>{val}</td>'
            html += '</tr>'
        html += '</table></div>'
        st.markdown(html, unsafe_allow_html=True)

        # Заголовок для стального кольца
        if not df_steel.empty:
            st.markdown(f'<div {table_title_style}>Расчёт стального кольца</div>', unsafe_allow_html=True)
            # Перемещаем столбец "Несущая способность кольца" в конец для стального кольца
            steel_columns_order = [col for col in df_steel.columns if col != 'Несущая способность кольца, N<sub>p,t</sub>, кН']
            steel_columns_order.append('Несущая способность кольца, N<sub>p,t</sub>, кН')
            df_steel = df_steel[steel_columns_order]
            
            html2 = '''
            <style>
            .rings-table-wrapper { overflow-x: auto; }
            .rings-table {
                min-width: 900px;
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                background: #fff;
                border-radius: 8px;
                box-shadow: 0 1px 6px 0 rgba(0,0,0,0.04);
                border: 1px solid #e0e0e0;
                font-size: 0.88em;
                table-layout: fixed;
            }
            .rings-table th {
                background: #f6f8fa;
                color: #222;
                font-weight: 600;
                padding: 10px 12px;
                border-bottom: 1.5px solid #eaecef;
                border-right: 1px solid #e0e0e0;
                white-space: normal;
                word-wrap: break-word;
            }
            .rings-table td {
                padding: 8px 12px;
                border-bottom: 1px solid #f0f0f0;
                color: #222;
                border-right: 1px solid #e0e0e0;
                text-align: center;
                white-space: normal;
                word-wrap: break-word;
            }
            .rings-table th:first-child,
            .rings-table td:first-child {
                width: 75px;
            }
            </style>
            <div class="rings-table-wrapper">
            <table class="rings-table">
            <tr>
            '''
            for col in df_steel.columns:
                top, bottom = header_map.get(col, (col, ""))
                html2 += f'<th style="vertical-align:middle; padding-bottom:2px; text-align:center;">'
                html2 += f'<div style="font-weight:600; text-align:center; vertical-align:middle;">{top}</div>'
                if bottom:
                    html2 += f'<div style="font-size:0.92em; color:#888; font-weight:400; text-align:center; vertical-align:middle;">{bottom}</div>'
                html2 += '</th>'
            html2 += '</tr>'
            for _, row in df_steel.iterrows():
                html2 += '<tr>'
                for val in row:
                    html2 += f'<td>{val}</td>'
                html2 += '</tr>'
            html2 += '</table></div>'
            st.markdown(html2, unsafe_allow_html=True)

        # Заголовок для арматуры
        df_rebar = df[df['№'].str.startswith('Арм')].copy()  # Берем только строки, начинающиеся с "Арм"
        if not df_rebar.empty:
            # Оставляем только нужные столбцы для арматуры
            columns_to_keep = [
                '№',
                'Площадь сечения, A, мм²',
                'Температура, T, °C',
                'Коэффициент условий работы стали, γ<sub>st</sub>',
                'Расчётное сопротивление стали, R<sub>su</sub>, МПа',
                'Модуль упругости стали, E<sub>s,t</sub>, МПа',
                'Момент инерции, I, м⁴',
                'Жёсткость кольца, EI, кН·м²',
                'Несущая способность кольца, N<sub>p,t</sub>, кН'
            ]
            df_rebar = df_rebar[columns_to_keep]
            
            st.markdown(f'<div {table_title_style}>Расчёт арматуры</div>', unsafe_allow_html=True)
            html3 = '''
            <style>
            .rings-table-wrapper { overflow-x: auto; }
            .rings-table {
                min-width: 900px;
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                background: #fff;
                border-radius: 8px;
                box-shadow: 0 1px 6px 0 rgba(0,0,0,0.04);
                border: 1px solid #e0e0e0;
                font-size: 0.88em;
                table-layout: fixed;
            }
            .rings-table th {
                background: #f6f8fa;
                color: #222;
                font-weight: 600;
                padding: 10px 12px;
                border-bottom: 1.5px solid #eaecef;
                border-right: 1px solid #e0e0e0;
                white-space: normal;
                word-wrap: break-word;
            }
            .rings-table td {
                padding: 8px 12px;
                border-bottom: 1px solid #f0f0f0;
                color: #222;
                border-right: 1px solid #e0e0e0;
                text-align: center;
                white-space: normal;
                word-wrap: break-word;
            }
            .rings-table th:first-child,
            .rings-table td:first-child {
                width: 75px;
            }
            </style>
            <div class="rings-table-wrapper">
            <table class="rings-table">
            <tr>
            '''
            for col in df_rebar.columns:
                top, bottom = header_map.get(col, (col, ""))
                html3 += f'<th style="vertical-align:middle; padding-bottom:2px; text-align:center;">'
                html3 += f'<div style="font-weight:600; text-align:center; vertical-align:middle;">{top}</div>'
                if bottom:
                    html3 += f'<div style="font-size:0.92em; color:#888; font-weight:400; text-align:center; vertical-align:middle;">{bottom}</div>'
                html3 += '</th>'
            html3 += '</tr>'
            for _, row in df_rebar.iterrows():
                html3 += '<tr>'
                for val in row:
                    html3 += f'<td>{val}</td>'
                html3 += '</tr>'
            html3 += '</table></div>'
            st.markdown(html3, unsafe_allow_html=True)
    else:
        st.info("Данные для таблицы по кольцам отсутствуют. Проверьте входные данные и наличие thermal_data.json.")

    # --- Центрированный и одинаковый стиль заголовка для сводной таблицы ---
    st.markdown(f'<div {table_title_style}>Результаты расчёта</div>', unsafe_allow_html=True)
    # Убираем старый subheader
    summary_data_list = []
    stiffness_sum_check = 0.0
    for row in table_data_list:
        val_str = row.get("Жёсткость кольца, EI, кН·м²", "N/A")
        if val_str != "N/A":
            try:
                stiffness_sum_check += float(val_str)
            except ValueError:
                pass
    
    # Используем сумму из таблицы для отображения
    final_total_stiffness_display = stiffness_sum_check

    if N_final_for_summary_table is not None:
        summary_data_list.append({"Показатель": "Несущая способность колонны", "Значение": f"{N_final_for_summary_table:.1f} кН"})
    else:
        summary_data_list.append({"Показатель": "Несущая способность колонны", "Значение": "N/A"})

    if final_total_stiffness_display > 0:
        summary_data_list.append({"Показатель": "Полная жесткость сечения (EI)", "Значение": f"{final_total_stiffness_display:.1f} кН·м²"})
    else:
        summary_data_list.append({"Показатель": "Полная жесткость сечения (EI)", "Значение": "N/A"})

    if N_cr_for_summary_table is not None:
        summary_data_list.append({"Показатель": "Критическая сила", "Значение": f"{N_cr_for_summary_table:.1f} кН"})
    else:
        summary_data_list.append({"Показатель": "Критическая сила", "Значение": "N/A"})

    if reduction_coeff_for_summary_table is not None:
        summary_data_list.append({"Показатель": "Понижающий коэффициент", "Значение": f"{reduction_coeff_for_summary_table:.3f}"})
    else:
        summary_data_list.append({"Показатель": "Понижающий коэффициент", "Значение": "N/A"})
        
    if slenderness_for_summary_table is not None:
        summary_data_list.append({"Показатель": "Условная гибкость", "Значение": f"{slenderness_for_summary_table:.3f}"})
    else:
        summary_data_list.append({"Показатель": "Условная гибкость", "Значение": "N/A"})

    if summary_data_list:
        summary_table_html = '''
        <style>
        .summary-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 1px 6px 0 rgba(0,0,0,0.04);
            border: 1px solid #e0e0e0;
            font-size: 1.08em;
        }
        .summary-table th {
            background: #f6f8fa;
            color: #222;
            font-weight: 600;
            padding: 12px 18px;
            border-bottom: 1.5px solid #eaecef;
            border-right: 1px solid #e0e0e0;
        }
        .summary-table th:last-child {
            border-right: none;
        }
        .summary-table td {
            padding: 10px 18px;
            border-bottom: 1px solid #f0f0f0;
            color: #222;
            border-right: 1px solid #e0e0e0;
        }
        .summary-table td:last-child {
            border-right: none;
        }
        .summary-table tr:last-child td {
            border-bottom: none;
        }
        /* Скругление и обводка только на внешних углах */
        .summary-table tr:first-child th:first-child {
            border-top-left-radius: 8px;
            border-left: 1px solid #e0e0e0;
            border-top: 1px solid #e0e0e0;
        }
        .summary-table tr:first-child th:last-child {
            border-top-right-radius: 8px;
            border-right: 1px solid #e0e0e0;
            border-top: 1px solid #e0e0e0;
        }
        .summary-table tr:last-child td:first-child {
            border-bottom-left-radius: 8px;
            border-left: 1px solid #e0e0e0;
            border-bottom: 1px solid #e0e0e0;
        }
        .summary-table tr:last-child td:last-child {
            border-bottom-right-radius: 8px;
            border-right: 1px solid #e0e0e0;
            border-bottom: 1px solid #e0e0e0;
        }
        .summary-table tr:hover td {
            background: #f0f6ff;
            transition: background 0.2s;
        }
        </style>
        <table class="summary-table">
            <tr><th>Показатель</th><th>Значение</th></tr>
        '''
        for row in summary_data_list:
            summary_table_html += f'<tr><td>{row["Показатель"]}</td><td>{row["Значение"]}</td></tr>'
        summary_table_html += '</table>'
        st.markdown(summary_table_html, unsafe_allow_html=True)

with tab2:
    # --- Центрированный заголовок графика ---
    st.markdown('<div style="text-align:center; font-size:1.25em; font-weight:700; font-family:Segoe UI, Arial, sans-serif; margin-bottom:0.5em;">График несущей способности от времени</div>', unsafe_allow_html=True)

    if closest_data and N_final_list and times:
        chart_df = pd.DataFrame({
            "Время, мин": times,
            "Несущая способность, кН": N_final_list
        })
        chart_df = chart_df.set_index("Время, мин").reset_index()
        # --- Поиск предела огнестойкости ---
        fire_limit_time = None
        for i in range(1, len(chart_df)):
            prev = chart_df.iloc[i-1]
            curr = chart_df.iloc[i]
            if prev["Несущая способность, кН"] >= normative_load and curr["Несущая способность, кН"] < normative_load:
                t1, t2 = prev["Время, мин"], curr["Время, мин"]
                n1, n2 = prev["Несущая способность, кН"], curr["Несущая способность, кН"]
                if n1 != n2:
                    fire_limit_time = t1 + (normative_load - n1) * (t2 - t1) / (n2 - n1)
                else:
                    fire_limit_time = t1
                break
        # Основная линия
        line = alt.Chart(chart_df).mark_line(point=True, color="#d62728", strokeWidth=3).encode(
            x=alt.X("Время, мин", axis=alt.Axis(title="Время огневого воздействия, мин", titleFontSize=16)),
            y=alt.Y("Несущая способность, кН", axis=alt.Axis(title="Несущая способность, кН", titleFontSize=16)),
            tooltip=["Время, мин", "Несущая способность, кН"]
        )
        # Горизонтальная линия нормативной нагрузки
        norm_line = alt.Chart(pd.DataFrame({
            "y": [normative_load],
        })).mark_rule(color="#1f77b4", strokeDash=[2,2], size=2).encode(
            y="y"
        )
        # Вертикальная линия предела огнестойкости
        if fire_limit_time is not None:
            fire_limit_df = pd.DataFrame({
                "x": [fire_limit_time],
                "y1": [normative_load],
                "y0": [0]
            })
            fire_limit_vline = alt.Chart(fire_limit_df).mark_rule(color="#2ca02c", strokeDash=[1,0], size=3).encode(
                x="x",
                y="y1",
                y2="y0"
            )
            fire_limit_point = alt.Chart(fire_limit_df).mark_point(filled=True, color="#2ca02c", size=80).encode(
                x="x",
                y="y1"
            )
            chart = (line + norm_line + fire_limit_vline + fire_limit_point).properties(height=800).interactive()
        else:
            chart = (line + norm_line).properties(height=800).interactive()
        st.altair_chart(chart, use_container_width=True)
        # --- Легенда под графиком ---
        legend_html = f'''
        <div style="display:flex; flex-direction:column; align-items:center; margin-top:0.5em;">
            <div style="display:flex; align-items:center; gap:1em;">
                <span style="display:inline-block; width:24px; height:4px; background:#2ca02c; border-radius:2px;"></span>
                <span style="font-size:1em;">Зелёная линия — предел огнестойкости{f': {fire_limit_time:.1f} мин' if fire_limit_time is not None else ''}</span>
            </div>
            <div style="display:flex; align-items:center; gap:1em; margin-top:0.3em;">
                <span style="display:inline-block; width:24px; height:4px; background: repeating-linear-gradient(90deg, #1f77b4, #1f77b4 8px, transparent 8px, transparent 16px); border-radius:2px;"></span>
                <span style="font-size:1em;">Синяя пунктирная линия — нормативная нагрузка: {normative_load} кН</span>
            </div>
        </div>
        '''
        st.markdown(legend_html, unsafe_allow_html=True)
    elif 'fig' in locals():
        st.pyplot(fig)

with tab3:
    st.markdown('<div style="text-align:center; font-size:1.25em; font-weight:700; font-family:Segoe UI, Arial, sans-serif; margin-bottom:0.5em;">Коэффициент запаса прочности</div>', unsafe_allow_html=True)

    if closest_data and N_final_list and normative_load > 0 and 'n_safety_list' in dir():
        # DataFrame для графика
        df_safety = pd.DataFrame({
            'Время, мин': times,
            'Коэффициент запаса n': n_safety_list
        })

        # Найти предел огнестойкости (когда n = 1)
        fire_resistance_limit_n = None
        for i in range(1, len(n_safety_list)):
            if n_safety_list[i-1] >= 1 and n_safety_list[i] < 1:
                # Линейная интерполяция
                t0, t1 = times[i-1], times[i]
                n0, n1 = n_safety_list[i-1], n_safety_list[i]
                if n1 != n0:
                    fire_resistance_limit_n = t0 + (1 - n0) * (t1 - t0) / (n1 - n0)
                break

        # Основная линия графика
        line = alt.Chart(df_safety).mark_line(
            point=True, color="#1f77b4", strokeWidth=3
        ).encode(
            x=alt.X('Время, мин:Q', title='Время, мин'),
            y=alt.Y('Коэффициент запаса n:Q', title='Коэффициент запаса прочности n')
        )

        # Горизонтальная линия n = 1
        rule_data = pd.DataFrame({'y': [1]})
        rule = alt.Chart(rule_data).mark_rule(
            color='red', strokeDash=[5, 5], strokeWidth=2
        ).encode(y='y:Q')

        # Текст "n = 1"
        text_n1 = alt.Chart(pd.DataFrame({
            'x': [max(times) * 0.9],
            'y': [1.05],
            'text': ['n = 1']
        })).mark_text(
            color='red', fontSize=12, fontWeight='bold'
        ).encode(x='x:Q', y='y:Q', text='text:N')

        chart = (line + rule + text_n1).properties(height=400)

        # Вертикальная линия предела огнестойкости
        if fire_resistance_limit_n is not None:
            vline_data = pd.DataFrame({'x': [fire_resistance_limit_n]})
            vline = alt.Chart(vline_data).mark_rule(
                color='green', strokeDash=[3, 3], strokeWidth=2
            ).encode(x='x:Q')
            chart = chart + vline

        st.altair_chart(chart, use_container_width=True)

        # Информационный блок
        col1, col2 = st.columns(2)
        with col1:
            if fire_resistance_limit_n is not None:
                st.metric("Предел огнестойкости", f"{fire_resistance_limit_n:.1f} мин")
            else:
                st.info("Предел огнестойкости не достигнут в расчётном диапазоне")
        with col2:
            if n_safety_list:
                st.metric("Начальный запас прочности", f"{n_safety_list[0]:.2f}")
    else:
        st.warning("Недостаточно данных для построения графика. Убедитесь, что нагрузка > 0.")

with tab4:
    st.markdown('<div style="text-align:center; font-size:1.25em; font-weight:700; font-family:Segoe UI, Arial, sans-serif; margin-bottom:0.5em;">График нагрева сечения</div>', unsafe_allow_html=True)
    
    if closest_data:
        # Подготовка данных для графика температур
        temp_data_list = []
        for r in closest_data:
            t = r.get('time_minutes')
            if isinstance(t, (int, float)):
                item = {'Время, мин': t / 60.0}
                # Собираем температуры
                for k, label in [
                    ('temp_t1', 'Сталь (t1)'),
                    ('temp_t2', 'Б1 (t2)'),
                    ('temp_t3', 'Б2 (t3)'),
                    ('temp_t4', 'Арматура (t4)'),
                    ('temp_t5', 'Б3 (t5)'),
                    ('temp_t6', 'Б4 (t6)'),
                    ('temp_t7', 'Б5 (t7)'),
                    ('temp_t8', 'Б6 (t8)'),
                    ('temp_t9', 'Б7 (t9)'),
                ]:
                    val = r.get(k)
                    if val is not None:
                        item[label] = val
                temp_data_list.append(item)
        
        if temp_data_list:
            df_temps = pd.DataFrame(temp_data_list)
            df_temps = df_temps.sort_values('Время, мин')
            
            fig_temps = go.Figure()
            
            # Добавляем линии
            for col in df_temps.columns:
                if col == 'Время, мин':
                    continue
                fig_temps.add_trace(go.Scatter(
                    x=df_temps['Время, мин'], 
                    y=df_temps[col], 
                    mode='lines', 
                    name=col
                ))
            
            fig_temps.update_layout(
                height=600,
                xaxis_title="Время, мин",
                yaxis_title="Температура, °C",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                hovermode="x unified"
            )
            
            st.plotly_chart(fig_temps, use_container_width=True)
    else:
         st.info("Нет данных для отображения графика прогрева.")

with tab5:
    st.markdown('<div style="text-align:center; font-size:1.25em; font-weight:700; font-family:Segoe UI, Arial, sans-serif; margin-bottom:0.5em;">Сечение колонны</div>', unsafe_allow_html=True)
    
    # Параметры круга
    radius = diameter / 2  # мм
    center_x, center_y = 0, 0

    # Создаем точки для внешнего круга
    theta = np.linspace(0, 2*np.pi, 100)
    x_outer = center_x + radius * np.cos(theta)
    y_outer = center_y + radius * np.sin(theta)

    # Создаем точки для первого внутреннего круга (с учетом толщины стальной стенки)
    x_inner1 = center_x + (radius - thickness) * np.cos(theta)
    y_inner1 = center_y + (radius - thickness) * np.sin(theta)

    # Создаем точки для второго внутреннего круга (еще на 10 мм меньше)
    x_inner2 = center_x + (radius - thickness - 10) * np.cos(theta)
    y_inner2 = center_y + (radius - thickness - 10) * np.sin(theta)

    # Создаем точки для третьего внутреннего круга (еще на 20 мм меньше)
    x_inner3 = center_x + (radius - thickness - 30) * np.cos(theta)
    y_inner3 = center_y + (radius - thickness - 30) * np.sin(theta)

    # Создаем точки для четвертого внутреннего круга (еще на 20 мм меньше)
    x_inner4 = center_x + (radius - thickness - 50) * np.cos(theta)
    y_inner4 = center_y + (radius - thickness - 50) * np.sin(theta)

    # Создаем точки для пятого внутреннего круга (еще на 20 мм меньше)
    x_inner5 = center_x + (radius - thickness - 70) * np.cos(theta)
    y_inner5 = center_y + (radius - thickness - 70) * np.sin(theta)

    # Создаем точки для шестого внутреннего круга (еще на 20 мм меньше)
    x_inner6 = center_x + (radius - thickness - 90) * np.cos(theta)
    y_inner6 = center_y + (radius - thickness - 90) * np.sin(theta)

    # Создаем точки для седьмого внутреннего круга (еще на 30 мм меньше)
    x_inner7 = center_x + (radius - thickness - 110) * np.cos(theta)
    y_inner7 = center_y + (radius - thickness - 110) * np.sin(theta)

    # Создаем точки для слоев без армирования
    x_inner1_no = center_x + (radius - thickness) * np.cos(theta)
    y_inner1_no = center_y + (radius - thickness) * np.sin(theta)

    x_inner2_no = center_x + (radius - thickness - 20) * np.cos(theta)
    y_inner2_no = center_y + (radius - thickness - 20) * np.sin(theta)

    x_inner3_no = center_x + (radius - thickness - 40) * np.cos(theta)
    y_inner3_no = center_y + (radius - thickness - 40) * np.sin(theta)

    x_inner4_no = center_x + (radius - thickness - 60) * np.cos(theta)
    y_inner4_no = center_y + (radius - thickness - 60) * np.sin(theta)

    x_inner5_no = center_x + (radius - thickness - 80) * np.cos(theta)
    y_inner5_no = center_y + (radius - thickness - 80) * np.sin(theta)

    x_inner6_no = center_x + (radius - thickness - 100) * np.cos(theta)
    y_inner6_no = center_y + (radius - thickness - 100) * np.sin(theta)

    x_inner7_no = center_x + (radius - thickness - 120) * np.cos(theta)
    y_inner7_no = center_y + (radius - thickness - 120) * np.sin(theta)

    # Создаем точки армирования
    reinforcement_radius = radius - thickness - 40  # Учитываем толщину стенки
    reinforcement_theta = np.linspace(0, 2*np.pi, rebar_count, endpoint=False)
    reinforcement_x = center_x + reinforcement_radius * np.cos(reinforcement_theta)
    reinforcement_y = center_y + reinforcement_radius * np.sin(reinforcement_theta)

    # Добавляем переключатель
    if use_reinforcement:
        show_reinforcement = st.radio("Отображение армирования:", ["С армированием", "Без армирования"])
    else:
        show_reinforcement = "Без армирования"

    fig = go.Figure()

    # Внешний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_outer, y=y_outer,
        fill='toself',
        fillcolor='rgb(0,0,0)',
        line=dict(width=0),
        showlegend=False
    ))

    if show_reinforcement == "С армированием":
        # Первый внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner1, y=y_inner1,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Второй внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner2, y=y_inner2,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Третий внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner3, y=y_inner3,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Четвертый внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner4, y=y_inner4,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Пятый внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner5, y=y_inner5,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Шестой внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner6, y=y_inner6,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Седьмой внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner7, y=y_inner7,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Контур первого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner1, y=y_inner1,
            mode='lines',
            line=dict(width=2, color='red'),
            name=f'Стальная стенка (t={thickness} мм)',
            showlegend=False
        ))

        # Контур второго внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner2, y=y_inner2,
            mode='lines',
            line=dict(width=2, color='green'),
            name='Второй внутренний контур',
            showlegend=False
        ))

        # Контур третьего внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner3, y=y_inner3,
            mode='lines',
            line=dict(width=2, color='purple'),
            name='Третий внутренний контур',
            showlegend=False
        ))

        # Контур четвертого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner4, y=y_inner4,
            mode='lines',
            line=dict(width=2, color='orange'),
            name='Четвертый внутренний контур',
            showlegend=False
        ))

        # Контур пятого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner5, y=y_inner5,
            mode='lines',
            line=dict(width=2, color='brown'),
            name='Пятый внутренний контур',
            showlegend=False
        ))

        # Контур шестого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner6, y=y_inner6,
            mode='lines',
            line=dict(width=2, color='pink'),
            name='Шестой внутренний контур',
            showlegend=False
        ))

        # Контур седьмого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner7, y=y_inner7,
            mode='lines',
            line=dict(width=2, color='gray'),
            name='Седьмой внутренний контур',
            showlegend=True
        ))

        # Точки армирования
        fig.add_trace(go.Scatter(
            x=reinforcement_x, y=reinforcement_y,
            mode='markers',
            marker=dict(
                size=rebar_diameter,
                color='red',
                line=dict(width=1, color='black')
            ),
            name=f'Армирование {rebar_count}Ø{rebar_diameter}',
            showlegend=True
        ))

    else:  # Без армирования
        # Первый внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner1_no, y=y_inner1_no,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Второй внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner2_no, y=y_inner2_no,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Третий внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner3_no, y=y_inner3_no,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Четвертый внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner4_no, y=y_inner4_no,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Пятый внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner5_no, y=y_inner5_no,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Шестой внутренний круг (заливка)
        fig.add_trace(go.Scatter(
            x=x_inner6_no, y=y_inner6_no,
            fill='toself',
            fillcolor='rgb(210,209,205)',
            line=dict(width=0),
            showlegend=False
        ))

        # Контур первого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner1_no, y=y_inner1_no,
            mode='lines',
            line=dict(width=2, color='red'),
            name=f'Стальная стенка (t={thickness} мм)',
            showlegend=True
        ))

        # Контур второго внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner2_no, y=y_inner2_no,
            mode='lines',
            line=dict(width=2, color='green'),
            name='Второй внутренний контур',
            showlegend=True
        ))

        # Контур третьего внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner3_no, y=y_inner3_no,
            mode='lines',
            line=dict(width=2, color='purple'),
            name='Третий внутренний контур',
            showlegend=True
        ))

        # Контур четвертого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner4_no, y=y_inner4_no,
            mode='lines',
            line=dict(width=2, color='orange'),
            name='Четвертый внутренний контур',
            showlegend=True
        ))

        # Контур пятого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner5_no, y=y_inner5_no,
            mode='lines',
            line=dict(width=2, color='brown'),
            name='Пятый внутренний контур',
            showlegend=True
        ))

        # Контур шестого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner6_no, y=y_inner6_no,
            mode='lines',
            line=dict(width=2, color='pink'),
            name='Шестой внутренний контур',
            showlegend=True
        ))

        # Контур седьмого внутреннего круга
        fig.add_trace(go.Scatter(
            x=x_inner7_no, y=y_inner7_no,
            mode='lines',
            line=dict(width=2, color='gray'),
            name='Седьмой внутренний контур',
            showlegend=True
        ))

    # Контур внешнего круга
    fig.add_trace(go.Scatter(
        x=x_outer, y=y_outer,
        mode='lines',
        line=dict(width=2, color='black'),
        name=f'Внешний контур (D={diameter} мм)',
        showlegend=True
    ))

    # Настройки осей
    axis_range = radius * 1.1  # Делаем запас 10% от радиуса
    tick_step = max(50, round(radius / 5))  # Шаг делений зависит от радиуса
    tick_values = list(range(-int(radius), int(radius) + tick_step, tick_step))
    
    fig.update_xaxes(
        range=[-axis_range, axis_range],
        tickvals=tick_values,
        title="X, мм"
    )
    fig.update_yaxes(
        range=[-axis_range, axis_range],
        tickvals=tick_values,
        title="Y, мм"
    )

    fig.update_layout(
        width=600, height=600,
        plot_bgcolor='white',
        showlegend=False,  # Скрываем стандартную легенду
        margin=dict(l=40, r=40, t=40, b=120),
        autosize=True,
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            showgrid=True,
            zeroline=True,
            showline=True,
            mirror=True,
            scaleanchor="y",
            scaleratio=1,
            constrain="domain"  # Ограничиваем область отображения
        ),
        yaxis=dict(
            showgrid=True,
            zeroline=True,
            showline=True,
            mirror=True,
            constrain="domain"  # Ограничиваем область отображения
        )
    )

    # Создаем контейнер для центрирования
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.plotly_chart(fig, use_container_width=True)
    
    # Создаем HTML/CSS легенду
    legend_html = f'''
    <style>
    .custom-legend {{
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 20px;
        margin-top: 0;
        padding: 10px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .legend-column {{
        display: flex;
        flex-direction: column;
        gap: 10px;
    }}
    .legend-item {{
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
    }}
    .legend-color {{
        width: 20px;
        height: 3px;
        border-radius: 2px;
    }}
    </style>
    <div class="custom-legend">
        <div class="legend-column">
            <div class="legend-item">
                <div class="legend-color" style="background: black;"></div>
                <span>Внешний контур (D={diameter} мм)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: red;"></div>
                <span>Стальная стенка (t={thickness} мм)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: green;"></div>
                <span>Второй внутренний контур</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: purple;"></div>
                <span>Третий внутренний контур</span>
            </div>
        </div>
        <div class="legend-column">
            <div class="legend-item">
                <div class="legend-color" style="background: orange;"></div>
                <span>Четвертый внутренний контур</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: brown;"></div>
                <span>Пятый внутренний контур</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: pink;"></div>
                <span>Шестой внутренний контур</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: gray;"></div>
                <span>Седьмой внутренний контур</span>
            </div>
        </div>
    </div>
    '''
    
    st.markdown(legend_html, unsafe_allow_html=True)

with tab6:
    st.markdown("""
    ### О проекте
    - Современный расчёт огнестойкости трубобетонных колонн
    - Используются реальные температурные данные
    - Все расчёты автоматизированы
    - [Streamlit](https://streamlit.io/) — быстрый и удобный фреймворк для визуализации инженерных расчётов
    """)
    st.info("Данный расчёт является демонстрационным и не заменяет нормативный расчёт по СП или другим стандартам.") 