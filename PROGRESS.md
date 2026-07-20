# DriveBook — PROGRESS.md
> Последнее обновление: 2026-07-19 (сессия 2)

---

## 1. Что сделано (накопительно)

### 1.1 Бэкенд — API

#### Миграции (все 5 применены к БД)
| Файл | Что содержит |
|------|-------------|
| `001_init.sql` | `instructors`, `slots`, `bookings`, `idempotency_records` |
| `002_v2.sql` | `schools`, `waitlist`, `events`, `rate_limit_buckets` (старая схема), `webhook_log`, `cache_meta` |
| `003_slot_visibility.sql` | колонка `is_hidden` в `slots` |
| `004_auth_and_audit.sql` | `users`, `sessions`, `audit_log`, `hide_requests` |
| `005_fix_rate_limit.sql` | ✅ **СЕССИЯ 2** — пересоздаёт `rate_limit_buckets` с `UNIQUE(bucket_key, window_start)` |

> **Важно**: миграция 005 применена вручную через `docker exec drivebook-db psql ...`.
> При следующем `make migrate` будет пропущена (если `schema_migrations` уже её содержит).
> При `make seed --force` применится автоматически (seed.py запускает все .sql).

#### `api/app/routes.py` — исправления сессии 2 (коммит `816616b`)
- `require_supervisor()` переписан: проверяет Bearer token ИЛИ Basic Auth против таблицы `users` с проверкой `role IN ('supervisor', 'admin')` — раньше проверял только env-var пароль
- `GET /v1/admin/audit-log` переключён с `require_admin` на `require_supervisor`
- `_rec()` дедуплицирован: единственное определение на уровне модуля (строка 78), локальная копия внутри `admin_dashboard` удалена

#### `api/app/seed.py` — исправление (коммит `a2e7f5c`)
- Добавлен `import os` (отсутствовал — вызывал `NameError` в `_hashpw()`)

#### `Makefile` (коммит `816616b`, в корне проекта)
```makefile
VENV = api/.venv
PY   = $(VENV)/bin/python
make install   # создаёт venv, ставит зависимости
make run       # cd api && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100 --reload
make migrate   # python -m app.migrate
make seed      # python -m app.seed --force
```

### 1.2 Виджет — полная переработка (сессия 2)

#### `widget/widget.css` (коммит `61a114a`) — BSM Mobile v3.0
- Переменные: `--c-orange: #F07C00`, `--c-orange-dark: #D46E00`, `--c-orange-lite: #FFF0E0`
- `.db-shell`: `min-height: 100dvh`, `max-width: 430px`, `margin: 0 auto`
- 5-сегментный прогресс-бар `.db-progress` / `.db-progress-seg.on`
- `.db-nav`, `.db-nav-back`, `.db-nav-lang`, `.db-nav-exit`
- Сегментный контрол `.db-tabs` / `.db-tab.active`
- Карточки дат `.db-date-card.active`, стрелки `.db-date-arrow`
- Слоты `.db-slot-row.active` (оранжевая рамка + box-shadow)
- Форма `.db-form`, `.db-field`, `.db-field-terms`, `.db-terms-label`, `.db-terms-body`, `.db-terms-link`
- Кастомный чекбокс с SVG-галочкой при `:checked`
- Фиксированный CTA `.db-foot-cta` (sticky, gradient снизу)
- Экран поздравления `.db-congrats-wrap`, детали `.db-details-card`

#### `widget/widget.js` (коммиты `5f2172b`, `a2e7f5c`, `564215b`, `77f5bc8`) — BSM Mobile v3.0
**Архитектура потока:**
```
renderLessonType() [шаг 1]
  └→ renderBest() [шаг 2] — 3 ближайших слота, filterLastSlot()
       └→ renderContact() — напрямую из best
  └→ renderInstructors() [шаг 3]
       └→ renderSlotPicker() [шаг 4] — календарь инструктора
            └→ renderContact() [шаг 5]
                 └→ renderDone()
```

**Ключевые решения:**
- `state.lessonType`: `"standard"` | `"exam"` — отправляется в API как `lesson_type`
- `state.fromInstructor`: флаг для правильной навигации «Назад» из контактной формы
- `filterLastSlot(slots)`: группирует по дням, убирает последний слот каждого дня
- Поле «откуда забрать» → `notes` в теле запроса к API
- **Удалено**: подсказка про подарочный вариант (не MVP)

**Исправления сессии 2 (коммит `77f5bc8`):**
- `api()` helper: парсит Pydantic 422-ошибку как массив `[{loc, msg, type}]` → показывает `detail[0].msg` вместо «HTTP 422»
- Телефонное поле: `type="tel" inputmode="numeric"` + фронтенд-проверка (≥8 цифр) перед отправкой
- **T&C блок** в `renderContact()`:
  - Текст адаптирован под законодательство Молдовы (Legea nr. 133/2011), не скопирован с BSM UK
  - Клик по ссылке разворачивает текст условий инлайн
  - Кнопка «ЗАПИСАТЬСЯ» / «REZERVĂ ACUM» заблокирована, пока чекбокс не отмечен
  - Переводы в `STR.ro` / `STR.ru`: `termsLabel`, `termsLink`, `termsText`, `termsRequired`, `phoneInvalid`

#### `widget/book.html` (коммит `581e500`)
- Шрифт Titillium Web (Google Fonts)
- `viewport-fit=cover`, `apple-mobile-web-app-capable`
- Загружает `widget.css?v=3.0` и `widget.js?v=3.0`

---

## 2. Текущее состояние БД

**Схема**: миграции 001–005 применены.
**Данные**: 100 инструкторов, ~7 000 слотов на 14 дней, users (admin/supervisor/100 инструкторов).

> `rate_limit_buckets` теперь имеет `UNIQUE(bucket_key, window_start)` — booking endpoint работает корректно.

---

## 3. Git-статус (на конец сессии 2026-07-19)

### Закоммичено (чисто)
| Коммит | Что |
|--------|-----|
| `77f5bc8` | Миграция 005, виджет: 422-парсинг, телефон, T&C |
| `564215b` | Удаление gift hint |
| `a2e7f5c` | Lesson type первый экран, pickup-поле, `import os` в seed |
| `581e500` | book.html Stage 3 |
| `5f2172b` | widget.js Stage 2 |
| `61a114a` | widget.css Stage 1 |
| `7f6c267` | Дедупликация `_rec()` |
| `816616b` | Makefile, `require_supervisor` |

### НЕ закоммичено (modified/untracked)
| Файл | Статус | Примечание |
|------|--------|-----------|
| `AGENTS.md` | modified | Обновлён в ходе предыдущих сессий — проверить и закоммитить |
| `Makefile` | modified | Содержит незакоммиченные правки поверх коммита `816616b` |
| `admin/index.html` | modified | Обновлён в рамках этапа v2 — не закоммичен |
| `api/app/config.py` | modified | Правки конфигурации |
| `api/app/main.py` | modified | Правки запуска/mount |
| `api/app/services.py` | modified | Большие изменения v2 (best_slots, rate_limit и др.) |
| `widget/i18n.js` | modified | Файл i18n (возможно устарел — виджет использует встроенный STR) |
| `api/migrations/003_slot_visibility.sql` | untracked | Создан, но не добавлен в git |
| `api/migrations/004_auth_and_audit.sql` | untracked | Создан, но не добавлен в git |
| `PROGRESS.md` | untracked | Этот файл |

---

## 4. Следующие шаги (для новой сессии)

### Приоритет 1 — Зафиксировать незакоммиченные файлы
```bash
git add api/migrations/003_slot_visibility.sql \
        api/migrations/004_auth_and_audit.sql \
        api/app/services.py api/app/main.py \
        api/app/config.py admin/index.html \
        AGENTS.md Makefile widget/i18n.js PROGRESS.md
git diff --stat  # убедиться, что нет ничего лишнего
git commit -m "chore: commit v2 backend + admin changes"
```

### Приоритет 2 — Деплой на Railway для демо клиентам
1. Создать проект на railway.app → подключить GitHub repo
2. Add PostgreSQL plugin — Railway выставит `DATABASE_URL` автоматически
3. Прописать start command: `cd api && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Убедиться, что `api/app/config.py` читает `DATABASE_URL` из окружения (проверить)
5. После деплоя выполнить в Railway Console: `python -m app.seed --force`
6. Проверить `https://<your-app>.railway.app/book`

### Приоритет 3 — Мелкие улучшения UX перед показом клиентам
- [ ] Экран подтверждения: добавить номер телефона для связи с инструктором (если хотим)
- [ ] Кнопка «Назад» на первом экране (lesson type) — сейчас скрыта, но ✕ есть
- [ ] `widget/i18n.js` — либо удалить (не используется виджетом), либо синхронизировать со `STR` в `widget.js`
- [ ] `experience_years` в `GET /v1/instructors/{id}` response (сейчас не возвращается)

### Приоритет 4 — Продуктовые фичи (Post-MVP)
- [ ] Email/SMS подтверждение студенту после бронирования
- [ ] Ссылка отмены бронирования (`cancel_token` уже в схеме)
- [ ] Напоминания за 24ч и 2ч (`reminder_24h_sent_at` / `reminder_2h_sent_at` уже в схеме)
- [ ] WebSocket real-time для notification badge в admin

---

## 5. Как запускать локально

```bash
# 1. Поднять БД (если не запущена)
cd /Users/ghivi/projects/drivebook
docker compose up -d db

# 2. Установить зависимости (первый раз)
make install

# 3. Применить миграции (если новые)
make migrate

# 4. Запустить сервер
make run
# → http://127.0.0.1:8100/book   — виджет бронирования
# → http://127.0.0.1:8100/admin  — панель администратора

# Если нужно пересеять данные (СОТРЁТ всё!)
make seed
```

### Учётные данные
| Роль | Логин | Пароль |
|------|-------|--------|
| admin | `admin` | `drivebook-admin` |
| supervisor | `supervisor` | `supervisor-secret` |
| instructor | `instructor_001` … `instructor_100` | `instructor` |
