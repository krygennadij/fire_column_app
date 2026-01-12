# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Streamlit web application for calculating fire resistance of concrete-filled steel tubular (CFST) columns. The app calculates load-bearing capacity under fire conditions using thermal data and material properties.

## Commands

```bash
# Run the application
streamlit run app/main.py

# Install dependencies
pip install -r requirements.txt

# Convert thermal data from Excel to JSON
python convert_excel_to_json.py
```

## Architecture

### Core Modules (app/)

- **main.py** - Streamlit UI with 6 tabs: detailed calculation, capacity graph, safety factor graph, temperature graph, cross-section visualization, about
- **config.py** - Dataclass-based configuration: `GeometryLimits`, `MaterialConstants`, `CalculationConfig`, `DefaultValues`
- **calculations.py** - Core calculation functions: `calculate_capacity_for_time()`, `calculate_stiffness_for_time()`, `calculate_final_capacity()`
- **utils.py** - Helper functions: section geometry, temperature-dependent material coefficients, concrete ring discretization
- **validation.py** - Input validation with `validate_all_inputs()`

### Data Flow

1. User inputs geometry (diameter, thickness, height) and material properties (steel/concrete strength)
2. App loads thermal data from `thermal_data/*.json` matching closest available diameter×thickness
3. Calculation discretizes concrete core into 7 rings with temperatures from thermal record
4. Each ring's capacity and stiffness computed using temperature-dependent coefficients
5. Final capacity reduced by slenderness factor

### Thermal Data Format

JSON files named `{diameter}x{thickness}.json` contain arrays:
```json
{
  "time_minutes": 0,
  "temp_t1": 20.0,  // Steel shell temperature
  "temp_t2": 20.0,  // Concrete ring B1 (outer)
  "temp_t3": 20.0,  // Concrete ring B2
  "temp_t4": 20.0,  // Rebar temperature
  "temp_t5": 20.0,  // Concrete ring B3
  ...
  "temp_t9": 20.0   // Concrete ring B7 (inner)
}
```

### Key Calculations

- **Safety factor**: n = N_capacity / N_load (fire resistance limit when n = 1)
- **Slenderness reduction**: Uses interpolation table in `get_reduction_coeff()`
- **Material coefficients**: `steel_working_condition_coeff()` and `concrete_working_condition_coeff()` reduce strength with temperature

## Language

The codebase and UI are in Russian. Variable names and comments use transliterated Russian terms (e.g., `normative_load`, `rebar_strength_normative`).
