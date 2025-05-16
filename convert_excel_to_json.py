import pandas as pd
import json
import os
from pathlib import Path

def convert_excel_to_json(excel_file):
    # Читаем Excel файл
    df = pd.read_excel(excel_file)
    
    # Выводим информацию о структуре файла
    print(f"\nСтруктура файла {excel_file.name}:")
    print("Столбцы:", df.columns.tolist())
    print("Первые 2 строки:")
    print(df.head(2))
    
    # Создаем список для хранения данных
    data = []
    
    # Проходим по каждой строке
    for _, row in df.iterrows():
        # Создаем словарь для текущей записи
        record = {
            "time_minutes": int(row['Время, сек'])
        }
        for i in range(1, 7):
            key = i if i in row else str(i)
            record[f"temp_t{i}"] = float(row[key])
        data.append(record)
    
    return data

def main():
    # Путь к директории с Excel файлами
    excel_dir = Path("thermal xlm")
    
    # Создаем директорию для JSON файлов, если её нет
    json_dir = Path("thermal_data")
    json_dir.mkdir(exist_ok=True)
    
    # Проходим по всем Excel файлам
    for excel_file in excel_dir.glob("*.xlsx"):
        # Получаем имя файла без расширения
        file_name = excel_file.stem
        
        # Конвертируем Excel в JSON
        data = convert_excel_to_json(excel_file)
        
        # Сохраняем JSON файл
        json_file = json_dir / f"{file_name}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        print(f"Конвертирован файл: {excel_file.name} -> {json_file.name}")

if __name__ == "__main__":
    main() 