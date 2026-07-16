# pgAdmin в Docker Compose

Основной `compose.yaml` поднимает официальный `dpage/pgadmin4:9.16` вместе с MeSync.
Отдельная команда запуска не нужна:

```bash
docker compose up --detach --build
```

Интерфейс доступен на `/admin/psql/` через общий gateway. Сам порт pgAdmin `5050` и порт
PostgreSQL `5432` не публикуются на хосте.

## Настройки

- `MESYNC_PGADMIN_EMAIL` — email входа, по умолчанию `admin@mesync.app`.
- `MESYNC_PGADMIN_PASSWORD` — отдельный пароль; если пуст, используется
  `MESYNC_ADMIN_PASSWORD`.
- `MESYNC_POSTGRES_DB` и `MESYNC_POSTGRES_USER` — автоматически попадают в
  предустановленное подключение `MeSync PostgreSQL`; внутренний host/port — `db:5432`.
- `MESYNC_POSTGRES_PASSWORD` — передаётся password-exec helper-у и не сохраняется в
  declarative `servers.json`.

Данные самого pgAdmin хранятся в `mesync_pgadmin_data`. Начальные email/пароль и
`servers.json` импортируются только при первом запуске пустого тома. Смену пароля после
инициализации выполняйте в интерфейсе pgAdmin. Для полного сброса только pgAdmin:

```bash
docker compose stop pgadmin
docker compose rm --force pgadmin
docker volume rm mesync_pgadmin_data
docker compose up --detach pgadmin gateway
```

Удаление `mesync_pgadmin_data` не удаляет PostgreSQL-данные из `mesync_postgres_data`.
