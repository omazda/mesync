# MAX ⇄ Telegram Sync — mini-app (web)

Панель управления ботом-синхронизатором. React 18 + Vite (JS/JSX). Запускается внутри
**MAX** (`window.WebApp`) и **Telegram Mini Apps** (`window.Telegram.WebApp`), а в
обычном браузере показывает переход к настроенным ссылкам на ботов.

## Разработка

```bash
cd web
npm install
npm run dev        # http://localhost:5174
```

В dev-режиме запросы `/api/*` проксируются на `http://127.0.0.1:8090`
(control-API). Запустить backend:

```bash
# из корня репозитория
PYTHONPATH=src .venv/bin/uvicorn control.asgi:app --port 8090     # только API
# или единый процесс (оба бота + API + общий стор):
.venv/bin/python run_app.py
```

## Сборка

```bash
npm run build      # → web/dist (статика, base относительный)
npm run preview
```

## Структура

- `src/host/` — слой над хостами (тема, requestContact, нативная «Назад», хаптика, initData).
- `src/api/` — клиент control-API (`client.js`).
- `src/store/` — zustand-стор (фаза/гейтинг, ресурсы, навигация).
- `src/components/` — дизайн-система (Icon, ui.jsx) на токенах `src/styles/theme.css`.
- `src/nav/` + `src/screens/` — стек-навигатор и 14 экранов (S1–S13 + SH) + листы.

Гейтинг: `loading → auth (S1–S4) → paywall (S5, жёсткий гейт) → app (вкладки
Правила/Источники/Настройки)`. Контракт API — в `src/api/client.js`, бэкенд — `src/control`.
