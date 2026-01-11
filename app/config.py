"""
Конфигурация расчётов огнестойкости сталетрубобетонной колонны.

Содержит все константы, используемые в расчётах.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class GeometryLimits:
    """Ограничения геометрических параметров"""
    MIN_DIAMETER_MM: float = 200.0
    MAX_DIAMETER_MM: float = 1200.0
    MIN_THICKNESS_MM: float = 3.0
    MAX_THICKNESS_MM: float = 30.0
    MIN_HEIGHT_M: float = 0.5
    MAX_HEIGHT_M: float = 30.0


@dataclass
class MaterialConstants:
    """Константы материалов"""
    # Защитный слой бетона по СП 63.13330
    REBAR_COVER_MM: float = 35.0

    # Расстояние от центра до арматуры для стандартного сечения
    REBAR_NOMINAL_DISTANCE_MM: float = 210.0

    # Количество стержней по умолчанию (8 стержней по окружности)
    DEFAULT_REBAR_COUNT: int = 8

    # Диаметр одного стержня арматуры по умолчанию
    DEFAULT_REBAR_DIAMETER_MM: int = 10


@dataclass
class CalculationConfig:
    """Конфигурация расчётов"""
    # Количество бетонных колец для дискретизации сечения
    NUM_CONCRETE_RINGS: int = 7

    # Толщины колец в мм (от внешнего к внутреннему)
    # None для последнего кольца означает "занять всё оставшееся пространство"
    RING_THICKNESSES_MM: List[Optional[float]] = None

    def __post_init__(self):
        if self.RING_THICKNESSES_MM is None:
            # Конфигурация по умолчанию: 10, 20, 20, 20, 20, 20, остаток
            self.RING_THICKNESSES_MM = [10.0, 20.0, 20.0, 20.0, 20.0, 20.0, None]


@dataclass
class DefaultValues:
    """Значения по умолчанию для UI"""
    DIAMETER_MM: float = 355.6
    THICKNESS_MM: float = 9.5
    HEIGHT_M: float = 2.5
    EFFECTIVE_LENGTH_COEFF: float = 0.7

    STEEL_STRENGTH_MPA: int = 355
    STEEL_ELASTIC_MODULUS_MPA: int = 210000
    CONCRETE_STRENGTH_MPA: float = 42.0

    NORMATIVE_LOAD_KN: float = 900.0
    FIRE_EXPOSURE_TIME_MIN: int = 0


# Глобальные экземпляры конфигурации
GEOMETRY_LIMITS = GeometryLimits()
MATERIAL_CONSTANTS = MaterialConstants()
CALCULATION_CONFIG = CalculationConfig()
DEFAULT_VALUES = DefaultValues()
