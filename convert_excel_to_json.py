import pandas as pd
import json
import os
from pathlib import Path

def convert_excel_to_json(excel_file):
    try:
        # Читаем Excel файл
        df = pd.read_excel(excel_file)
        
        # Выводим информацию о структуре файла
        print(f"\nСтруктура файла {excel_file.name}:")
        print("Столбцы:", df.columns.tolist())
        print("Первые 2 строки:")
        print(df.head(2))
        
        # Определяем маппинг столбцов
        # temp_t1 -> Сталь
        # temp_t2 -> Б1
        # temp_t3 -> Б2
        # temp_t4 -> Армирование
        # temp_t5 -> Б3
        # ...
        
        column_mapping = {
            'Сталь': 'temp_t1',
            'Б1': 'temp_t2',
            'Б2': 'temp_t3',
            'Армирование': 'temp_t4',
            'Б3': 'temp_t5',
            'Б4': 'temp_t6',
            'Б5': 'temp_t7',
            'Б6': 'temp_t8',
            'Б7': 'temp_t9'
        }
        
        # Проверяем наличие всех необходимых столбцов
        missing_columns = [col for col in column_mapping.keys() if col not in df.columns]
        if missing_columns:
            print(f"Предупреждение: отсутствуют столбцы {missing_columns}")
        
        # Создаем список для хранения данных
        data = []
        
        # Проходим по каждой строке
        for index, row in df.iterrows():
            try:
                # Создаем словарь для текущей записи
                record = {
                    "time_minutes": int(row['Время, сек'])
                }
                
                # Добавляем температурные точки согласно маппингу
                for col_name, json_key in column_mapping.items():
                    if col_name in row:
                        record[json_key] = float(row[col_name])
                    else:
                        # Если столбца нет, можно заполнить нулем или пропустить
                        # В данном случае лучше пропустить или вывести предупреждение
                        pass
                        
                data.append(record)
            except Exception as e:
                print(f"Ошибка в строке {index + 2}: {str(e)}")
                print(f"Содержимое строки: {row.to_dict()}")
                raise
        
        return data
    except Exception as e:
        print(f"Ошибка при обработке файла {excel_file}: {str(e)}")
        raise

def main():
    try:
        # Получаем текущую директорию скрипта
        current_dir = Path(__file__).parent
        
        # Путь к директории с Excel файлами
        excel_dir = current_dir / "thermal xlm"
        
        # Создаем директорию для JSON файлов, если её нет
        json_dir = current_dir / "thermal_data"
        json_dir.mkdir(exist_ok=True)
        
        # Проходим по всем Excel файлам
        for excel_file in excel_dir.glob("*.xlsx"):
            try:
                print(f"\nОбработка файла: {excel_file}")
                # Получаем имя файла без расширения
                file_name = excel_file.stem
                
                # Конвертируем Excel в JSON
                data = convert_excel_to_json(excel_file)
                
                # Сохраняем JSON файл
                json_file = json_dir / f"{file_name}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                
                print(f"Конвертирован файл: {excel_file.name} -> {json_file.name}")
            except Exception as e:
                print(f"Ошибка при обработке файла {excel_file}: {str(e)}")
                continue
    except Exception as e:
        print(f"Общая ошибка: {str(e)}")

if __name__ == "__main__":
    main()