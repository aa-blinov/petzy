# Локальная разработка фронтенда

## Быстрый старт

1. **Запустите бэкенд через Docker:**
   ```bash
   docker-compose up -d db web
   ```

2. **Установите зависимости фронтенда (если еще не установлены):**
   ```bash
   cd frontend
   npm install
   ```

3. **Запустите dev server:**
   ```bash
   npm run dev
   ```

4. **Откройте браузер:**
   - React приложение: http://localhost:5173/
   - Flask API: http://localhost:5001/api/

## Настройка для локальной разработки

Конфигурация автоматически переключается между dev и production:

- **Dev mode** (`npm run dev`): 
  - `base: '/'` - без префикса
  - `basename: '/'` в React Router
  - Порт: 5173 (Vite default)
  
- **Production build** (`npm run build`):
  - `base: '/app/'` - с префиксом для Docker
  - `basename: '/app'` в React Router
  - Собирается для nginx

## Прокси API

В dev режиме все запросы к `/api/*` автоматически проксируются на `http://localhost:5001` (Flask бэкенд).

## Структура портов

- **5173** - Vite dev server (фронтенд, локально)
- **3000** - Nginx (production, через Docker)
- **5001** - Flask бэкенд (через Docker)
- **27017** - MongoDB (через Docker)

## Отладка

- **React DevTools**: установите расширение для браузера
- **Network tab**: проверяйте запросы к API в DevTools
- **Console**: логи из React приложения
- **Hot Module Replacement (HMR)**: автоматическая перезагрузка при изменении кода

## Горячая перезагрузка

Vite автоматически перезагружает страницу при изменении файлов в `src/`. Изменения применяются мгновенно без полной перезагрузки страницы.

## Остановка

Для остановки dev server нажмите `Ctrl+C` в терминале.

Для остановки Docker контейнеров:
```bash
docker-compose stop
# или
docker-compose down
```

