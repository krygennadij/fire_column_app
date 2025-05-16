import pandas as pd
import json
import os

# Имя исходного Excel файла и целевого JSON файла
EXCEL_FILE_NAME = "thermal.xlsx" # Убедитесь, что это правильное имя вашего файла
JSON_FILE_NAME = "thermal_data.json"

# Путь к текущей директории (где лежит этот скрипт)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EXCEL_FILE_PATH = os.path.join(BASE_DIR, EXCEL_FILE_NAME)
JSON_FILE_PATH = os.path.join(BASE_DIR, JSON_FILE_NAME)

def convert_thermal_data():
    print(f"--- Converter: Attempting to read Excel file: {EXCEL_FILE_PATH} ---")
    if not os.path.exists(EXCEL_FILE_PATH):
        print(f"!!! Converter: Excel file not found at {EXCEL_FILE_PATH}. Aborting. !!!")
        return

    try:
        # Читаем первый лист Excel файла
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=0)
        print(f"--- Converter: Excel file read successfully. Columns found: {df.columns.tolist()} ---")

        # Ожидаемые имена столбцов (должны совпадать с именами в вашем Excel)
        time_col_excel = 'Время, сек' # ИЗМЕНЕНО: Соответствует вашему файлу
        temp_cols_excel_prefix = ''    # ИЗМЕНЕНО: Префикса нет, у вас просто номера 1, 2, ...
        
        # Создаем маппинг для переименования столбцов в нужный формат, если требуется
        # Ключи в JSON должны быть 'time_minutes', 'temp_t1', ..., 'temp_t12'
        column_rename_map = {time_col_excel: 'time_minutes'}
        
        # Колонки температур в Excel могут быть числами или строками '1', '2', ...
        # Мы будем проверять и те, и другие варианты при формировании карты и списка cols_to_process
        cols_to_process_from_excel = [time_col_excel]
        
        for i in range(1, 13):
            # Пытаемся найти столбец как число (если pandas так прочитал)
            if i in df.columns:
                excel_temp_col_name = i
            # Пытаемся найти столбец как строку (если pandas так прочитал или префикс был)
            elif f"{temp_cols_excel_prefix}{i}" in df.columns:
                excel_temp_col_name = f"{temp_cols_excel_prefix}{i}"
            else:
                # Если столбца нет ни как числа, ни как строки, пропускаем его для JSON
                print(f"--- Converter: Warning - Temperature column for T{i} not found in Excel as '{i}' or '{temp_cols_excel_prefix}{i}'. It will be missing in JSON or be None if added later. ---")
                continue # Пропускаем этот столбец, если его нет
            
            column_rename_map[excel_temp_col_name] = f"temp_t{i}"
            cols_to_process_from_excel.append(excel_temp_col_name)
        
        # Преобразуем все элементы в строки ПЕРЕД созданием set и сортировкой
        cols_to_process_from_excel_str = [str(col) for col in cols_to_process_from_excel]
        # Убираем дубликаты (уже как строки) и сортируем
        cols_to_process_from_excel_sorted_str = sorted(list(set(cols_to_process_from_excel_str)))

        # Теперь нужно найти, какие из этих строковых имен колонок реально есть в df.columns
        # df.columns тоже могут содержать смесь str и int, поэтому приводим их к строкам для сравнения
        df_column_names_as_str = [str(col) for col in df.columns]

        actual_excel_columns_present_str = [col_str for col_str in cols_to_process_from_excel_sorted_str if col_str in df_column_names_as_str]
        
        # Для дальнейшего использования в df_selected нам нужны оригинальные имена колонок (не обязательно строки)
        # Поэтому мы будем фильтровать оригинальный df.columns
        # Это немного усложняет, но так надежнее для DataFrame
        
        # Сначала восстановим карту из cols_to_process_from_excel_sorted_str обратно к оригинальным типам,
        # которые есть в df.columns
        original_cols_for_df_selection = []
        for col_name_str in actual_excel_columns_present_str:
            if col_name_str == time_col_excel: # Время всегда строка
                original_cols_for_df_selection.append(time_col_excel)
            else:
                # Для температурных столбцов пытаемся найти их в df.columns как int или str
                try:
                    col_as_int = int(col_name_str)
                    if col_as_int in df.columns:
                        original_cols_for_df_selection.append(col_as_int)
                        continue
                except ValueError:
                    pass # Не число, значит точно строка
                if col_name_str in df.columns: # Если это строка (или не нашлось как int)
                    original_cols_for_df_selection.append(col_name_str)
        
        actual_excel_columns_present = original_cols_for_df_selection

        if not actual_excel_columns_present or time_col_excel not in actual_excel_columns_present:
            print(f"!!! Converter: Essential columns ('{time_col_excel}' or temp columns) not found or processed. Aborting. !!!")
            print(f"--- Converter: Columns intended for processing (as strings): {cols_to_process_from_excel_sorted_str}")
            print(f"--- Converter: Actual columns found and selected for DataFrame: {actual_excel_columns_present}")
            return

        # Выбираем только нужные столбцы из DataFrame, используя оригинальные имена
        df_selected = df[actual_excel_columns_present]
        
        # Переименовываем столбцы для JSON
        # column_rename_map должен использовать оригинальные имена столбцов Excel как ключи
        # Перестроим column_rename_map на основе actual_excel_columns_present
        current_rename_map = {time_col_excel: 'time_minutes'}
        for col_original_name in actual_excel_columns_present:
            if col_original_name == time_col_excel:
                continue
            # Определяем, какой temp_tX соответствует этому столбцу
            # Это может быть немного сложно, если порядок нарушен, но попробуем по значению
            for i in range(1, 13):
                # Проверяем, совпадает ли строковое представление или числовое
                if str(col_original_name) == str(i): 
                    current_rename_map[col_original_name] = f"temp_t{i}"
                    break
        
        print(f"--- Converter: Rename map to be used: {current_rename_map} ---")
        df_renamed = df_selected.rename(columns=current_rename_map)
        
        # Заполняем отсутствующие столбцы temp_tX (если их меньше 12 в Excel) значением None
        for i in range(1, 13):
            json_col_name = f"temp_t{i}"
            if json_col_name not in df_renamed.columns:
                df_renamed[json_col_name] = None
                print(f"--- Converter: Added missing column '{json_col_name}' with None values for JSON. ---")

        # Конвертируем DataFrame в список словарей
        data_list = df_renamed.to_dict(orient='records')
        print(f"--- Converter: Data converted to list of {len(data_list)} records. ---")

        # Сохраняем в JSON файл
        with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=4)
        print(f"--- Converter: Data successfully saved to {JSON_FILE_PATH} ---")

    except Exception as e:
        print(f"!!! Converter: An error occurred: {e} !!!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    convert_thermal_data() 