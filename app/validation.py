"""
Валидация входных данных для расчётов огнестойкости.
"""

from typing import Tuple
from .config import GEOMETRY_LIMITS


class ValidationError(ValueError):
    """Исключение для ошибок валидации"""
    pass


def validate_geometry(
    diameter_mm: float,
    thickness_mm: float,
    height_m: float
) -> Tuple[bool, str]:
    """
    Валидация геометрических параметров колонны.

    Args:
        diameter_mm: Наружный диаметр колонны в мм
        thickness_mm: Толщина стенки в мм
        height_m: Высота колонны в м

    Returns:
        Кортеж (is_valid, error_message)
        is_valid: True если параметры корректны
        error_message: Описание ошибки (пустая строка если ошибок нет)
    """
    # Проверка диаметра
    if diameter_mm <= 0:
        return False, "❌ Диаметр должен быть положительным числом"

    if diameter_mm < GEOMETRY_LIMITS.MIN_DIAMETER_MM:
        return False, f"❌ Диаметр не может быть меньше {GEOMETRY_LIMITS.MIN_DIAMETER_MM} мм"

    if diameter_mm > GEOMETRY_LIMITS.MAX_DIAMETER_MM:
        return False, f"❌ Диаметр не может быть больше {GEOMETRY_LIMITS.MAX_DIAMETER_MM} мм"

    # Проверка толщины
    if thickness_mm <= 0:
        return False, "❌ Толщина стенки должна быть положительным числом"

    if thickness_mm < GEOMETRY_LIMITS.MIN_THICKNESS_MM:
        return False, f"❌ Толщина стенки не может быть меньше {GEOMETRY_LIMITS.MIN_THICKNESS_MM} мм"

    if thickness_mm > GEOMETRY_LIMITS.MAX_THICKNESS_MM:
        return False, f"❌ Толщина стенки не может быть больше {GEOMETRY_LIMITS.MAX_THICKNESS_MM} мм"

    # Проверка соотношения толщины и диаметра
    if thickness_mm >= diameter_mm / 2:
        return False, f"❌ Толщина стенки ({thickness_mm} мм) не может быть больше или равна радиусу колонны ({diameter_mm/2:.1f} мм)"

    # Проверка минимальной толщины ядра
    concrete_core_radius = (diameter_mm / 2) - thickness_mm
    if concrete_core_radius < 50:
        return False, f"❌ Радиус бетонного ядра слишком мал ({concrete_core_radius:.1f} мм). Увеличьте диаметр или уменьшите толщину стенки"

    # Проверка высоты
    if height_m <= 0:
        return False, "❌ Высота колонны должна быть положительным числом"

    if height_m < GEOMETRY_LIMITS.MIN_HEIGHT_M:
        return False, f"❌ Высота колонны не может быть меньше {GEOMETRY_LIMITS.MIN_HEIGHT_M} м"

    if height_m > GEOMETRY_LIMITS.MAX_HEIGHT_M:
        return False, f"❌ Высота колонны не может быть больше {GEOMETRY_LIMITS.MAX_HEIGHT_M} м"

    return True, ""


def validate_materials(
    steel_strength_mpa: float,
    steel_elastic_modulus_mpa: float,
    concrete_strength_mpa: float
) -> Tuple[bool, str]:
    """
    Валидация параметров материалов.

    Args:
        steel_strength_mpa: Нормативное сопротивление стали в МПа
        steel_elastic_modulus_mpa: Модуль упругости стали в МПа
        concrete_strength_mpa: Нормативное сопротивление бетона в МПа

    Returns:
        Кортеж (is_valid, error_message)
    """
    # Проверка прочности стали
    if steel_strength_mpa <= 0:
        return False, "❌ Прочность стали должна быть положительным числом"

    if steel_strength_mpa < 200:
        return False, "❌ Прочность стали слишком низкая (минимум 200 МПа)"

    if steel_strength_mpa > 1000:
        return False, "❌ Прочность стали слишком высокая (максимум 1000 МПа)"

    # Проверка модуля упругости
    if steel_elastic_modulus_mpa <= 0:
        return False, "❌ Модуль упругости стали должен быть положительным числом"

    if steel_elastic_modulus_mpa < 150000:
        return False, "❌ Модуль упругости стали слишком низкий (минимум 150000 МПа)"

    if steel_elastic_modulus_mpa > 250000:
        return False, "❌ Модуль упругости стали слишком высокий (максимум 250000 МПа)"

    # Проверка прочности бетона
    if concrete_strength_mpa <= 0:
        return False, "❌ Прочность бетона должна быть положительным числом"

    if concrete_strength_mpa < 5.0:
        return False, "❌ Прочность бетона слишком низкая (минимум 5 МПа)"

    if concrete_strength_mpa > 120.0:
        return False, "❌ Прочность бетона слишком высокая (максимум 120 МПа)"

    return True, ""


def validate_loads(
    normative_load_kn: float,
    fire_exposure_time_min: int
) -> Tuple[bool, str]:
    """
    Валидация нагрузок и времени пожара.

    Args:
        normative_load_kn: Нормативная нагрузка в кН
        fire_exposure_time_min: Время огневого воздействия в минутах

    Returns:
        Кортеж (is_valid, error_message)
    """
    # Проверка нагрузки
    if normative_load_kn < 0:
        return False, "❌ Нагрузка не может быть отрицательной"

    if normative_load_kn > 50000:
        return False, "❌ Нагрузка слишком велика (максимум 50000 кН)"

    # Проверка времени пожара
    if fire_exposure_time_min < 0:
        return False, "❌ Время пожара не может быть отрицательным"

    if fire_exposure_time_min > 360:
        return False, "❌ Время пожара слишком велико (максимум 360 минут)"

    return True, ""


def validate_reinforcement(
    rebar_count: int,
    rebar_diameter_mm: int,
    diameter_mm: float,
    thickness_mm: float
) -> Tuple[bool, str]:
    """
    Валидация параметров армирования.

    Args:
        rebar_count: Количество стержней арматуры
        rebar_diameter_mm: Диаметр стержня в мм
        diameter_mm: Диаметр колонны в мм
        thickness_mm: Толщина стенки в мм

    Returns:
        Кортеж (is_valid, error_message)
    """
    # Проверка количества стержней
    if rebar_count < 0:
        return False, "❌ Количество стержней не может быть отрицательным"

    if rebar_count > 40:
        return False, "❌ Слишком много стержней (максимум 40)"

    # Проверка диаметра стержня
    if rebar_diameter_mm < 4:
        return False, "❌ Диаметр стержня слишком мал (минимум 4 мм)"

    if rebar_diameter_mm > 60:
        return False, "❌ Диаметр стержня слишком велик (максимум 60 мм)"

    # Проверка размещения арматуры
    concrete_core_radius = (diameter_mm / 2) - thickness_mm
    if rebar_diameter_mm > concrete_core_radius:
        return False, f"❌ Диаметр стержня ({rebar_diameter_mm} мм) больше радиуса бетонного ядра ({concrete_core_radius:.1f} мм)"

    return True, ""


def validate_all_inputs(
    diameter_mm: float,
    thickness_mm: float,
    height_m: float,
    steel_strength_mpa: float,
    steel_elastic_modulus_mpa: float,
    concrete_strength_mpa: float,
    normative_load_kn: float,
    fire_exposure_time_min: int,
    use_reinforcement: bool = False,
    rebar_count: int = 0,
    rebar_diameter_mm: int = 10
) -> Tuple[bool, str]:
    """
    Комплексная валидация всех входных параметров.

    Returns:
        Кортеж (is_valid, error_message)
        error_message содержит первую найденную ошибку
    """
    # Валидация геометрии
    is_valid, error = validate_geometry(diameter_mm, thickness_mm, height_m)
    if not is_valid:
        return False, error

    # Валидация материалов
    is_valid, error = validate_materials(
        steel_strength_mpa,
        steel_elastic_modulus_mpa,
        concrete_strength_mpa
    )
    if not is_valid:
        return False, error

    # Валидация нагрузок
    is_valid, error = validate_loads(normative_load_kn, fire_exposure_time_min)
    if not is_valid:
        return False, error

    # Валидация армирования (если используется)
    if use_reinforcement:
        is_valid, error = validate_reinforcement(
            rebar_count,
            rebar_diameter_mm,
            diameter_mm,
            thickness_mm
        )
        if not is_valid:
            return False, error

    return True, ""
