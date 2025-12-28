# EvacGPT (React + TypeScript)

Современное приложение для мониторинга и оценки уровня пожарной опасности.

## Стек
- React + TypeScript
- Material UI
- Axios (для автодополнения адреса через Яндекс.Карты)

## Быстрый старт

1. Клонируй/создай папку и перейди в неё:
   ```bash
   mkdir evac-gpt-react && cd evac-gpt-react
   ```
2. Инициализируй проект:
   ```bash
   npx create-react-app . --template typescript
   ```
3. Установи зависимости:
   ```bash
   npm install @mui/material @mui/icons-material axios
   ```
4. Замени/создай файлы из этого репозитория (см. ниже).
5. Запусти:
   ```bash
   npm start
   ```

## Структура
- `src/components/AddressAutocomplete.tsx` — автодополнение адреса
- `src/components/EvacForm.tsx` — основная форма
- `src/components/ResultCard.tsx` — вывод результата
- `src/App.tsx` — главный компонент
- `src/main.tsx` — точка входа (от CRA/Vite)

## API-ключ Яндекс.Карт
Используется ключ: `14ca51d3-0445-4192-b619-98dac8c40a02` (можно заменить на свой в `AddressAutocomplete.tsx`)

---

## Файлы для копирования
(см. остальные файлы в этом проекте) 