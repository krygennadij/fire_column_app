import sys
import os
import json # Для загрузки JSON
import math
import pandas as pd
import matplotlib.pyplot as plt
import altair as alt
import streamlit as st
from pathlib import Path

# Добавляем корневую директорию проекта (fire_column_app) в sys.path
# Это позволяет Python корректно находить пакет 'app'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # Путь к текущему файлу (app/main.py)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR) # Путь к fire_column_app/
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.utils import calc_section, calc_capacity, discretize_concrete_core_into_rings, steel_ring_area, steel_working_condition_coeff, concrete_working_condition_coeff, concrete_strain_by_temp

# После импортов:
def get_reduction_coeff(slenderness):
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
    for i in range(1, len(table)):
        x0, y0 = table[i-1]
        x1, y1 = table[i]
        if x0 <= slenderness <= x1:
            return y0 + (y1 - y0) * (slenderness - x0) / (x1 - x0)
    return table[-1][1]

# 1. st.set_page_config() должен быть первой командой Streamlit
st.set_page_config(page_title="Расчёт огнестойкости сталетрубобетонной колонны", page_icon="🔥", layout="wide")

# --- Центрированный заголовок приложения ---
st.markdown('<div style="text-align:center; font-size:2em; font-weight:700; font-family:Segoe UI, Arial, sans-serif; margin-bottom:0.7em; margin-top:0.2em;">🔥 Расчёт огнестойкости сталетрубобетонной колонны</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Ввод исходных данных")
    diameter = st.number_input("Наружный диаметр, мм", min_value=200.0, max_value=500.0, value=244.5, step=0.1)
    thickness = st.number_input("Толщина стальной стенки, мм", min_value=3.0, max_value=9.0, value=6.3, step=0.1)
    steel_strength_normative = st.number_input("Нормативное сопротивление стали, МПа", min_value=200, max_value=600, value=355)
    steel_elastic_modulus = st.number_input("Модуль упругости стали, МПа", min_value=180000, max_value=220000, value=210000)
    concrete_strength_normative = st.number_input("Нормативное сопротивление бетона, МПа", min_value=10.0, max_value=60.0, value=42.0, step=0.1)
    height = st.number_input("Высота колонны, м", min_value=1.0, max_value=20.0, value=3.4, step=0.1)
    effective_length_coefficient = st.number_input("Коэффициент расчетной длины", min_value=0.5, max_value=2.0, value=0.7, step=0.1)
    normative_load = st.number_input("Нормативная нагрузка, кН", min_value=10.0, max_value=10000.0, value=635.0, step=0.1)
    fire_exposure_time = st.number_input("Время огневого воздействия, мин", min_value=0, max_value=240, value=60, step=5)

# Загрузка данных о температурах из JSON-файлов
def load_thermal_data():
    # Используем абсолютный путь к директории thermal_data
    thermal_dir = Path(PROJECT_ROOT) / "thermal_data"
    
    if not thermal_dir.exists():
        st.error(f"Директория {thermal_dir} не найдена!")
        return {}
        
    thermal_files = list(thermal_dir.glob("*.json"))
    if not thermal_files:
        st.error(f"JSON файлы не найдены в директории {thermal_dir}!")
        return {}
    
    thermal_data = {}
    for file in thermal_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Имя файла вида "200x3.json" -> диаметр 200, толщина 3
            name = file.stem
            diameter, thickness = map(int, name.split('x'))
            thermal_data[(diameter, thickness)] = data
        except Exception as e:
            st.error(f"Ошибка при загрузке файла {file.name}: {str(e)}")
            
    return thermal_data

# Функция для выбора ближайшего файла по геометрическим размерам
def get_closest_thermal_data(thermal_data, diameter, thickness):
    if not thermal_data:
        st.error("Нет доступных температурных данных!")
        return None
        
    available_diameters = sorted(set(d for d, _ in thermal_data.keys()))
    available_thicknesses = sorted(set(t for _, t in thermal_data.keys()))
    
    if not available_diameters or not available_thicknesses:
        st.error("Нет доступных размеров в температурных данных!")
        return None
    
    # Находим ближайший диаметр
    closest_diameter = min(available_diameters, key=lambda d: abs(d - diameter))
    # Находим ближайшую толщину
    closest_thickness = min(available_thicknesses, key=lambda t: abs(t - thickness))
    
    st.info(f"Температурные данные приняты для диаметра {closest_diameter} мм и толщины {closest_thickness} мм")
    
    return thermal_data.get((closest_diameter, closest_thickness), None)

# Загрузка данных о температурах
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
    num_rings=5,  # Устанавливаем 5 колец
    ring_thicknesses=[10, 20, 20, 20, None]  # Задаем толщины колец, последнее кольцо займет оставшееся пространство
)
temp_steel = None
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
        temp_steel = thermal_record.get('temp_t1')

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
if temp_steel is not None and isinstance(temp_steel, (int, float)):
    gamma_st = steel_working_condition_coeff(temp_steel)
    E_steel_fire = steel_elastic_modulus * gamma_st
    R_out_steel = diameter / 2
    R_in_steel = R_out_steel - thickness
    I_steel_ring = (math.pi / 4) * (R_out_steel**4 - R_in_steel**4) / 1e12  # м^4
    total_stiffness += I_steel_ring * E_steel_fire * 1e3  # кН·м²

# Критическая сила для выбранного fire_exposure_time
if total_stiffness > 0 and height > 0 and effective_length_coefficient > 0:
    # Это N_cr для сводной таблицы
    N_cr_for_summary_table = (math.pi ** 2) * total_stiffness / ((height * effective_length_coefficient) ** 2)
    
# Суммируем несущие способности всех колец для выбранного fire_exposure_time
N_total = 0.0 # N_total также будет специфичен для fire_exposure_time на этом этапе
if concrete_rings_details:
    for ring in concrete_rings_details:
        if ring['area_mm2'] is not None and ring['temperature_celsius'] is not None:
            gamma_bt = concrete_working_condition_coeff(ring['temperature_celsius'])
            f_cd_fire = gamma_bt * concrete_strength_normative
            area_m2 = ring['area_mm2'] / 1e6
            N_ring = area_m2 * f_cd_fire * 1e3  # кН
            N_total += N_ring
if temp_steel is not None and isinstance(temp_steel, (int, float)):
    area_steel_ring = steel_ring_area(diameter, thickness)
    gamma_st = steel_working_condition_coeff(temp_steel) if temp_steel is not None else None
    f_yd_fire = gamma_st * steel_strength_normative if gamma_st is not None else None
    E_steel_fire = steel_elastic_modulus * gamma_st if gamma_st is not None else None
    R_out_steel = diameter / 2
    R_in_steel = R_out_steel - thickness
    I_steel_ring = (math.pi / 4) * (R_out_steel**4 - R_in_steel**4) / 1e12
    area_steel_ring = steel_ring_area(diameter, thickness)
    N_steel_ring = area_steel_ring / 1e6 * f_yd_fire * 1e3 if (f_yd_fire is not None) else 0.0
    N_total += N_steel_ring

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
        for i in range(5):  # Изменено с 6 на 5 колец
            # Радиусы
            column_radius_mm = diameter / 2.0
            concrete_core_outer_radius_mm = column_radius_mm - thickness
            nominal_thicknesses_mm = [10.0, 20.0, 20.0, 20.0, None]  # Обновлены толщины
            if i < 4:  # Изменено с 5 на 4
                outer_r = concrete_core_outer_radius_mm - sum(t for t in nominal_thicknesses_mm[:i] if t is not None)
                inner_r = max(0.0, outer_r - (nominal_thicknesses_mm[i] if nominal_thicknesses_mm[i] is not None else outer_r))
            else:
                outer_r = concrete_core_outer_radius_mm - sum(t for t in nominal_thicknesses_mm[:i] if t is not None)
                inner_r = 0.0
            area = math.pi * (outer_r**2 - inner_r**2) if outer_r > inner_r else 0.0
            temp = None
            if thermal_record:
                temp = thermal_record.get(f'temp_t{i+2}')  # Изменено с i+1 на i+2 для соответствия нумерации
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
        # Критическая сила
        N_cr = (math.pi ** 2) * total_stiffness / ((height * effective_length_coefficient) ** 2) if (total_stiffness > 0 and height > 0 and effective_length_coefficient > 0) else 0.0
        # Условная гибкость
        slenderness = math.sqrt(N_total / N_cr) if N_cr > 0 else 0.0
        reduction_coeff = get_reduction_coeff(slenderness)
        N_final = N_total * reduction_coeff
        N_final_list.append(N_final)
    # График
    fig, ax = plt.subplots(figsize=(6,9))  # Увеличиваем высоту с 4.5 до 9
    ax.plot(times, N_final_list, marker='o', color='crimson')
    ax.set_xlabel('Время, мин')
    ax.set_ylabel('Несущая способность колонны, кН')
    ax.set_title('Зависимость несущей способности колонны от времени')
    ax.grid(True, linestyle='--', alpha=0.5)


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
# Данные по стальному кольцу
s_temp_steel = None
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
tab1, tab2, tab3 = st.tabs([
    "🧮 Расчёт по кольцам",
    "📈 График несущей способности",
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
        for col in df_concrete.columns:
            top, bottom = header_map.get(col, (col, ""))
            html += f'<th style="vertical-align:middle; padding-bottom:2px; text-align:center;">'
            html += f'<div style="font-weight:600; text-align:center; vertical-align:middle;">{top}</div>'
            if bottom:
                html += f'<div style="font-size:0.92em; color:#888; font-weight:400; text-align:center; vertical-align:middle;">{bottom}</div>'
            html += '</th>'
        html += '</tr>'
        for _, row in df_concrete.iterrows():
            html += '<tr>'
            for val in row:
                html += f'<td>{val}</td>'
            html += '</tr>'
        html += '</table></div>'
        st.markdown(html, unsafe_allow_html=True)

        # Заголовок для стального кольца
        if not df_steel.empty:
            st.markdown(f'<div {table_title_style}>Расчёт стального кольца</div>', unsafe_allow_html=True)
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
    else:
        st.info("Данные для таблицы по кольцам отсутствуют. Проверьте входные данные и наличие thermal_data.json.")

    # --- Центрированный и одинаковый стиль заголовка для сводной таблицы ---
    st.markdown(f'<div {table_title_style}>Результаты расчёта</div>', unsafe_allow_html=True)
    # Убираем старый subheader
    summary_data_list = []
    if N_final_for_summary_table is not None:
        summary_data_list.append({"Показатель": "Несущая способность колонны", "Значение": f"{N_final_for_summary_table:.1f} кН"})
    else:
        summary_data_list.append({"Показатель": "Несущая способность колонны", "Значение": "N/A"})

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
    st.markdown("""
    ### О проекте
    - Современный расчёт огнестойкости трубобетонных колонн
    - Используются реальные температурные данные
    - Все расчёты автоматизированы
    - [Streamlit](https://streamlit.io/) — быстрый и удобный фреймворк для визуализации инженерных расчётов
    """)
    st.info("Данный расчёт является демонстрационным и не заменяет нормативный расчёт по СП или другим стандартам.") 