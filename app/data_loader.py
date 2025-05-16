import pandas as pd
from sqlalchemy.orm import Session
from .models import ThermalData # Используем относительный импорт для models
import os

def populate_thermal_data_from_excel(session: Session, excel_file_path: str):
    print(f"--- DataLoader: Attempting to populate thermal data from {excel_file_path} ---")
    if not os.path.exists(excel_file_path):
        print(f"--- DataLoader: Excel file not found at {excel_file_path}. Skipping population. ---")
        return False

    # Проверяем, есть ли уже данные в таблице
    if session.query(ThermalData).first():
        print("--- DataLoader: ThermalData table is not empty. Skipping population. ---")
        return False

    try:
        # Предполагаем, что нужные данные на первом листе
        # и названия столбцов: 'Время', 'Т1', 'Т2', ..., 'Т12'
        df = pd.read_excel(excel_file_path, sheet_name=0)
        print(f"--- DataLoader: Excel file read successfully. Found columns: {df.columns.tolist()} ---")

        # Ожидаемые имена столбцов (можно адаптировать)
        time_col_name = 'Время' # или 'Time', 'time_minutes' и т.д.
        temp_col_names = [f'Т{i}' for i in range(1, 13)] # 'Т1', 'Т2', ...

        # Проверка наличия всех необходимых столбцов
        required_cols = [time_col_name] + temp_col_names
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"--- DataLoader: Missing required columns in Excel: {missing_cols}. Expected: {required_cols}. Found: {df.columns.tolist()}. Skipping population. ---")
            return False

        thermal_data_objects = []
        for _, row in df.iterrows():
            data_point = ThermalData(
                time_minutes=row[time_col_name],
                temp_t1=row[temp_col_names[0]],
                temp_t2=row[temp_col_names[1]],
                temp_t3=row[temp_col_names[2]],
                temp_t4=row[temp_col_names[3]],
                temp_t5=row[temp_col_names[4]],
                temp_t6=row[temp_col_names[5]],
                temp_t7=row[temp_col_names[6]],
            )
            thermal_data_objects.append(data_point)
        
        session.add_all(thermal_data_objects)
        session.commit()
        print(f"--- DataLoader: Successfully populated ThermalData table with {len(thermal_data_objects)} records. ---")
        return True
    except Exception as e:
        session.rollback()
        print(f"!!! DataLoader: Error populating ThermalData table: {e} !!!")
        import traceback
        traceback.print_exc()
        return False 