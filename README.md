# Fire Column App

## Запуск
1. Установи зависимости:  
   `pip install -r requirements.txt`
2. Перейди в директорию `fire_column_app`:
   `cd fire_column_app`
3. Запусти приложение:
   `python -m streamlit run app.main`

## Описание
Приложение для расчёта несущей способности трубобетонных колонн с возможностью сохранения истории расчётов в базу данных SQLite.

## Структура проекта

```
fire_column_app/
├── app/                  # Основной код приложения
│   ├── __init__.py       # Инициализация пакета app
│   ├── main.py           # Главный файл Streamlit приложения
│   ├── db.py             # Настройки базы данных (SQLAlchemy)
│   ├── models.py         # Модели данных (SQLAlchemy)
│   └── utils.py          # Вспомогательные функции
├── fire_column.db        # Файл базы данных SQLite (создается автоматически)
├── requirements.txt      # Зависимости проекта
└── README.md             # Этот файл
``` 