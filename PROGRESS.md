# DriveBook — PROGRESS.md
> Последнее обновление: 2026-07-20 (сессия 3)

---

## 0. Цветовая палитра

**Выбрано для MVP — Option D, navy + amber (road-sign):**
`primary #1B3A5C` (dark navy) · `accent #F2A93B` (amber, CTA) ·
`bg #F5F7FA` · `ink #22282E`. Применена во всех трёх местах: `widget/widget.css`,
`landing/landing.css`, `admin/index.html` — переменные переименованы
`--c-orange*` → `--c-amber*` (не просто перекрашены, чтобы имя не врало).

**Правило контраста**: amber используется для заливок/бордеров/CTA-фонов,
navy — для текста (amber-текст на белом фоне читается плохо, ~2:1). Кнопки
это делают буквально: amber-фон + navy-текст, вместо старого белого текста.
Футер landing — сплошная navy-полоса (не просто тон фона), это единственное
место, где второй цвет палитры получает настоящий, а не текстовый, акцент.

**Отклонённые варианты — рассмотреть после MVP при полном ребрендинге:**
- Option B, lime + asphalt: `accent #C8E85A` · `primary #2B2D2F` · `bg #F7F9F1` · `ink #1D1E1F`
- Option C, teal + coral: `primary #0F9E8E` · `accent #FF7A5C` · `bg #F4FAF9` · `ink #1C3532`

---

## 1. Что сделано (накопительно)

### 1.1 Бэкенд — API

#### Миграции (все 6 применены к БД)
| Файл | Что содержит |
|------|-------------|
| `001_init.sql` | `instructors`, `slots`, `bookings`, `idempotency_records` |
| `002_v2.sql` | `schools`, `waitlist`, `events`, `rate_limit_buckets` (старая схема), `webhook_log`, `cache_meta` |
| `003_slot_visibility.sql` | колонка `is_hidden` в `slots` |
| `004_auth_and_audit.sql` | `users`, `sessions`, `audit_log`, `hide_requests` |
| `005_fix_rate_limit.sql` | пересоздаёт `rate_limit_buckets` с `UNIQUE(bucket_key, window_start)` |
| `006_password_policy.sql` | ✅ **СЕССИЯ 3** — `users.must_change_password BOOLEAN` |

> 004 и 005 когда-то были применены вручную через `docker exec ... psql` и не
> были записаны в `schema_migrations`; в сессии 3 это исправлено (INSERT
> вручную в `schema_migrations`), так что `make migrate` теперь идёт чисто
> по всем 6 файлам без ручных вмешательств.

#### `api/app/services.py` — auth-исправления сессии 3
- **Критичный баг сессии 3**: `authenticate_user()` ловил `VerifyMismatchError`
  от argon2 в голый `except Exception: pass` — это означало, что **любой
  неверный пароль тихо принимался** для admin/supervisor/всех 100
  инструкторов. Исправлено: `_verify_password()` — общая функция проверки,
  явно возвращает `False` при несовпадении.
- `hash_password()` — общий helper (перенесён из `seed.py`, использовался
  дважды с риском разъехаться); используется и сидом, и новым
  `change_password()`.
- `change_password(conn, user_id, old_password, new_password)` — проверяет
  старый пароль, хэширует новый, сбрасывает `must_change_password`.
- `authenticate_user()` теперь возвращает и `must_change_password`.

#### `api/app/routes.py`
- **Ещё один найденный баг сессии 3**: `require_admin` проверял ТОЛЬКО
  `X-Admin-Password`/Basic Auth против env-переменной — никогда не принимал
  Bearer session token. Это ломало ВСЕ admin-эндпоинты (`/v1/admin/dashboard`,
  `/v1/admin/stats`, `/v1/admin/bookings`, `/v1/admin/events`,
  `/v1/admin/waitlist`, moderation, notifications) при логине через новую
  (и старую) форму username/password в `admin/index.html` — дашборд тихо
  падал с `Cannot read properties of undefined`. Исправлено: `require_admin`
  теперь принимает Bearer-сессию (роль `admin`) как основной путь,
  Basic/`X-Admin-Password` оставлен как fallback для внешних скриптов.
- `POST /v1/auth/change-password` — новый эндпоинт, `{old_password, new_password}` → Bearer.
- `POST /v1/auth/login` теперь возвращает `must_change_password` в `user`.

#### `api/app/seed.py`
- `admin`/`admin` — намеренно слабый бутстрап-пароль, `must_change_password=TRUE`
  (форсит смену при первом входе, поэтому хардкодить его OK).
- **Supervisor — теперь настоящий аккаунт, не демо**: логин/пароль читаются
  из `DRIVEBOOK_SUPERVISOR_USERNAME` / `DRIVEBOOK_SUPERVISOR_PASSWORD`
  (env / `.env`, см. `.env.example`), **без хардкод-фолбэка** — если не
  заданы, аккаунт просто не сеется (с явным предупреждением в консоли).
  При смене username между сессиями старая supervisor-строка переименовывается,
  а не дублируется (`UPDATE users SET username=$1 WHERE role='supervisor' AND username<>$1`).
- `.env` не подхватывался автоматически (в проекте не было `python-dotenv`/
  `load_dotenv()`) — добавлено `load_dotenv()` в начале `seed.py` +
  `python-dotenv` в `requirements.txt`.
- `_hashpw()` удалён, использует `svc.hash_password()`.

#### `api/requirements.txt`
- `argon2-cffi==25.1.0` — был установлен в venv, но не запинен; на чистой
  установке (Railway) сид бы тихо откатился на sha256-хэши.
- `python-dotenv==1.2.2` — см. выше.

### 1.2 Виджет (архитектура — сессия 2, палитра — сессия 3)

`widget/widget.css`/`widget/widget.js` — BSM Mobile v3.0, поток
`renderLessonType → renderBest/renderInstructors → renderSlotPicker → renderContact → renderDone`,
T&C-блок под молдавское законодательство, `api()` парсит Pydantic-422 как
массив. Подробности архитектуры не менялись с сессии 2.

**Сессия 3**: все `--c-orange*` → `--c-amber*` (навы+амбер, см. §0); несколько
`color: #fff` на amber-фоне заменены на `var(--c-navy)` для контраста.

### 1.3 NEW — Лендинг (`landing/`)

Мобилфёрст `landing/index.html` + `landing/landing.css`, структура по образцу
bsm.co.uk (референс дал скриншоты — сам сайт не фетчился, 403), но своя
палитра и контент под Молдову:
- Header: логотип PermisPro (navy), RO/RU-переключатель, "Контакты", "Войти" → `/admin`.
- Hero: navy→amber градиентный круг с SVG-рулём, заголовок/подзаголовок,
  2 CTA, 3 фичи-чипа.
- Секция бронирования: **живой** `DriveBookWidget.mount()` внутри карточки
  (не iframe) — переиспользует `/widget/widget.js`.
- "Так обучаешься с PermisPro" — 4 шага под молдавское лицензирование
  (запись онлайн → теория → практика → экзамен в ASP).
- Бар-мостик "Ты инструктор? → /admin".
- Footer: navy-полоса, about, адрес/телефон/email (**плейсхолдеры в `[ ]`,
  см. Приоритет 3**), соцсети FB/IG/TikTok (href="#", тоже плейсхолдер),
  3 колонки ссылок.
- Плавающая FAB-кнопка (Telegram/WhatsApp/Viber), разворачивается по клику.

**`api/app/main.py`**: `/` теперь отдаёт `landing/index.html` (раньше —
редирект на `/book`); добавлен `app.mount("/landing", ...)`. `/book`,
`/admin`, `/widget` не менялись.

**Баги embed-контекста виджета (найдены и исправлены только благодаря
живым скриншотам в браузере, не были бы пойманы текстовым ревью):**
- `.db-root`/`.db-shell` задают `min-height: 100dvh` — на весь viewport, что
  имеет смысл на отдельной `/book`, но внутри карточки на лендинге создавало
  гигантский пустой отступ. Исправлено scoped-оверрайдом `.lp-widget-frame .db-root, .db-shell { min-height: auto; }`.
- `.db-foot-cta` — `position: fixed` относительно viewport (не карточки):
  кнопка "CONTINUĂ" залипала бы над всей остальной страницей при скролле.
  Исправлено: `position: sticky` внутри `.lp-widget-frame`.
- У виджета был свой RO/RU-переключатель — второй, независимый от
  переключателя в шапке лендинга. Скрыт (`.lp-widget-frame .db-nav-lang { display: none; }`),
  переключатель в шапке теперь **перемонтирует** виджет с новым `lang`
  (публичного API для смены языка на лету у `widget.js` нет).

**Иллюстрация авто на карточке "Так обучаешься"**: на десктопе была
задана фиксированным `aspect-ratio: 4/5` независимо от высоты списка шагов
слева — оставляла пустое место снизу. Исправлено: `align-items: stretch`
на гриде + `aspect-ratio: auto` на карточке.

### 1.4 Admin-панель (`admin/index.html`)

- **Форма логина переписана**: убран `<select>` "Роль" (он маппил выбор
  роли на захардкоженный username — все "инструктор"-логины уходили на
  `instructor_001` независимо от того, кто реально логинился). Теперь
  обычные поля "Логин"/"Пароль"; роль определяет бэкенд по таблице `users`.
  Побочный эффект: теперь любой `instructor_NNN` может залогиниться под
  собой и увидеть свои слоты, а не всегда `instructor_001`.
- **Форс-смена пароля**: если `must_change_password=true` в ответе логина —
  показывается отдельный экран (новый пароль + подтверждение) вместо
  дашборда; проведено через `POST /v1/auth/change-password`.
- **Исправлен рендер ошибок**: `doLogin()` делал
  `loginErr.textContent = j.detail || 'Ошибка'` — если `detail` приходил
  массивом Pydantic-ошибок (422), рендерилось `[object Object]`. Добавлен
  `errMessage()` — строка напрямую, либо `.detail[0].msg` из массива,
  либо fallback. Тот же паттерн, что уже был в `widget.js`.
- Палитра navy/amber в инлайн `<style>` (см. §0); `.danger`/`.green`
  кнопки явно получили `color:#fff` (раньше наследовали белый цвет от
  базового `button` правила, которое теперь навy — без явного оверрайда
  красная/зелёная кнопка стала бы navy-на-red, нечитаемо).

---

## 2. Текущее состояние БД

**Схема**: миграции 001–006 применены.
**Данные** (после `make seed`, т.е. всегда `--force`): 100 инструкторов,
~14 дней слотов, `admin`/`admin` (`must_change_password=true`),
100× `instructor_NNN`/`instructor`.

**Supervisor НЕ засеян** — `.env` ещё не создан (ждём реальных логин/пароль
от пользователя, см. Приоритет 1 ниже). `.env.example` в репозитории
документирует нужные переменные.

---

## 3. Git-статус

Всё закоммичено, рабочее дерево чистое после этой сессии. Коммиты сессии 3
(в хронологическом порядке, начиная с хвоста сессии 2):

| Коммит | Что |
|--------|-----|
| `6981d62` | v2 auth backend: users/sessions/audit_log/hide_requests, argon2-verify баг **впервые исправлен здесь** |
| `4630905` | admin-панель переписана как role-based портал |
| `9de3c58` | синхронизация AGENTS.md/Makefile/widget-AGENTS.md/PROGRESS.md |
| `931af4e` | лендинг `landing/` добавлен, `/` отдаёт его вместо редиректа на `/book` |
| *(этот коммит)* | навy+amber палитра везде; фикс require_admin (Bearer-сессии); форс-смена пароля + `/v1/auth/change-password`; supervisor через `.env`/`DRIVEBOOK_SUPERVISOR_*`; фиксы embed-контекста виджета (100dvh, position:fixed, двойной RO/RU); фикс `[object Object]` в admin; car-illustration sizing |

---

## 4. Следующие шаги (для новой сессии)

### Приоритет 1 — задать реальные supervisor-креды
Пользователь сам выбирает логин/пароль (не подставлять автоматически).
Когда даст — создать локальный `.env` (скопировать `.env.example`), затем:
```bash
make seed   # уже включает --force
```
Проверить: `docker exec drivebook-db psql -U drivebook -d drivebook -c "SELECT username, role FROM users WHERE role='supervisor';"`

### Приоритет 2 — Деплой на Railway для демо клиентам
1. Создать проект на railway.app → подключить GitHub repo
2. Add PostgreSQL plugin — Railway выставит `DATABASE_URL` автоматически
3. Start command: `cd api && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Прописать `DRIVEBOOK_SUPERVISOR_USERNAME`/`DRIVEBOOK_SUPERVISOR_PASSWORD`
   в Railway env vars (иначе supervisor не засеется и там)
5. После деплоя: `python -m app.seed --force` в Railway Console
6. Проверить `https://<app>.railway.app/` (лендинг), `/book`, `/admin`

### Приоритет 3 — заполнить плейсхолдеры лендинга перед показом клиентам
- [ ] `landing/index.html`: адрес/телефон/email в футере (сейчас `[str. Exemplu 1]`, `[+373 XX XXX XXX]`, `[contact@permispro.md]`)
- [ ] Facebook/Instagram/TikTok — реальные ссылки вместо `href="#"`
- [ ] Telegram/WhatsApp/Viber в плавающей FAB-кнопке — реальные `t.me/…`, `wa.me/…`, `viber://…`

### Приоритет 4 — мелкие улучшения UX
- [ ] Экран подтверждения: номер телефона инструктора (если хотим)
- [ ] `experience_years` в `GET /v1/instructors/{id}` (сейчас не возвращается)
- [ ] Проверить/обновить `docs/DESIGN.md` — там всё ещё описан старый
      admin-auth (`HTTP Basic / X-Admin-Password vs schools.admin_password_hash`),
      не отражает Bearer-сессии

### Приоритет 5 — продуктовые фичи (post-MVP)
- [ ] Email/SMS подтверждение студенту после бронирования
- [ ] Ссылка отмены бронирования (`cancel_token` уже в схеме)
- [ ] Напоминания за 24ч и 2ч (`reminder_24h_sent_at`/`reminder_2h_sent_at` уже в схеме)
- [ ] WebSocket real-time для notification badge в admin
- [ ] Ребрендинг после MVP: рассмотреть Option B (lime+asphalt) / C (teal+coral), см. §0

### Note — делегирование worker.py
Для следующих похожих задач: не делегировать целиком визуальные/UI таски
(нужна живая проверка в браузере), но выносить в worker.py узкие
внутренние куски — перевод готового текста на другой язык, повторяющиеся
SVG-иконки, шаблонная разметка — если задача снова будет такого масштаба.

---

## 5. Как запускать локально

```bash
cd /Users/ghivi/projects/drivebook

# 1. Поднять БД (если не запущена)
docker compose up -d db

# 2. Установить зависимости (первый раз, или после изменений requirements.txt)
make install

# 3. Применить миграции (если новые)
make migrate

# 4. (опционально) настроить supervisor: cp .env.example .env, заполнить

# 5. Засеять данные (ВСЕГДА --force — сотрёт instructors/slots/bookings/users!)
make seed

# 6. Запустить сервер
make run
# → http://127.0.0.1:8100/        — лендинг (PermisPro)
# → http://127.0.0.1:8100/book    — виджет бронирования отдельно
# → http://127.0.0.1:8100/admin   — панель администратора
```

### Учётные данные
| Роль | Логин | Пароль |
|------|-------|--------|
| admin | `admin` | `admin` — форсит смену пароля при первом входе |
| supervisor | из `.env` | из `.env` — см. `.env.example`; без `.env` аккаунт не сеется |
| instructor | `instructor_001` … `instructor_100` | `instructor` |

Supervisor — реальный аккаунт, не демо: логин/пароль читаются из
`DRIVEBOOK_SUPERVISOR_USERNAME` / `DRIVEBOOK_SUPERVISOR_PASSWORD` (`.env`,
gitignored), без хардкод-фолбэка.
