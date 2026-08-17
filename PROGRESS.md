# DriveBook — PROGRESS.md
> Последнее обновление: 2026-07-20 (сессия 4)

---

## 0. Цветовая палитра

**Сессия 4 — landing полностью перерисован, палитра navy+amber на landing
заменена.** Текущее состояние: **два параллельных лендинга**, один и тот же
контент/структура/анимации, разные цветовые токены:

| Файл | Палитра | Статус |
|------|---------|--------|
| `landing/index.html` + `landing/tokens-sky.css` | **Sky + Tangerine** — `primary #1E88C7` · `accent #F26A0E` · `bg #F5FAFD` · `ink #17303D` | основной, показан владельцу |
| `landing/index-bsm.html` + `landing/tokens-bsm.css` | **Neutral + orange**, цвета взяты только со скриншотов bsm.co.uk (структура/контент НЕ копировались, только цвет) — `primary #3A3D42` (мягкий серый, НЕ чёрный/коричневый) · `accent #F26A0E` · `bg #F5F6F8` | запасной вариант / MVP для другого клиента |

**Accent (`#F26A0E`) теперь один и тот же во ВСЕХ поверхностях продукта** —
намеренное решение сессии 4, не только лендинг:
- `landing/tokens-sky.css` — `--c-accent`
- `landing/tokens-bsm.css` — `--c-accent`
- `widget/widget.css` — `--c-amber` (виджет монтируется живым внутри лендинга,
  разный оранжевый бросался в глаза сразу же)

`admin/index.html` **пока не тронут** — там всё ещё старый amber `#F2A93B`
(из сессии 3). Это известное расхождение, не критично (admin — внутренний
инструмент, не потребительский), но стоит выровнять при следующей правке
admin-панели.

**Архитектура токенов**: `landing/landing.css` — один файл component-CSS,
ничего не хардкодит по цвету (всё через `var(--c-*)`); `tokens-sky.css` /
`tokens-bsm.css` — только `:root{...}` с значениями, подключаются `<link>`
до `landing.css`. Помимо base-токенов есть шейп/спец-токены, которые тоже
различаются по палитре, а не просто цвет:
- `--r-btn` — радиус кнопок: `999px` (пилюля) у sky, `8px` (закруглённый
  прямоугольник) у bsm — у реального BSM кнопки не капсулы.
- `--cta-band-bg`, `--logo-mark-bg`, `--meter-fill-bg` — у sky это градиенты
  (`linear-gradient(...)`), у bsm — плоская заливка. Причина: на bsm.co.uk
  нет ни одного градиента нигде (кнопки, полосы — везде плоский цвет);
  для sky градиент — осознанный, отдельный выбор, не тронут.

**Ранее выбранная (сессия 3) navy+amber ещё жива в `admin/index.html`.**
Отклонённые/архивные варианты (lime+asphalt, teal+coral, исходный
navy+amber) — см. историю в git, не дублирую здесь.

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

**Сессия 4**: `--c-amber`/`--c-amber-dark`/`--c-amber-lite` перекрашены в
единый `#F26A0E`/`#D85A00`/`#FDE6D0` — тот же accent, что у обоих лендингов
(см. §0). `widget/widget.js` не менялся. Cache-buster в обоих
`landing/index*.html` (`?v=3.0` → `?v=3.1`) — без этого браузеры держали
старый `widget.css` в кеше и оранжевый визуально не совпадал с лендингом
даже после правки токенов.

### 1.3 Лендинг (`landing/`) — полностью перерисован в сессии 4

Версия сессии 3 (структура по мотивам bsm.co.uk, но так и не сверенная
с реальным сайтом — фетч давал 403) **заменена целиком**. Новая структура
скопирована по контенту/анимациям/mobile-first-подходу с независимого
референса `permispro-mobile-first.html` (тёплый, "менее пугающий" стиль:
confidence-card с барометром эмоций, road-timeline вместо статичных шагов),
а не с bsm.co.uk — см. §0 про то, откуда взят только цвет.

**Два файла лендинга, один общий CSS:**
- `landing/index.html` (Sky+Tangerine) + `landing/tokens-sky.css`
- `landing/index-bsm.html` (Neutral+orange) + `landing/tokens-bsm.css`
- `landing/landing.css` — общий для обоих, ни одного хардкод-цвета, всё
  через `var(--c-*)` и палитро-специфичные токены (см. §0)

**Порядок секций (сознательное решение — "виджет вторым скроллом"):**
nav → hero (confidence-card: барометр эмоций + счётчики) → **секция
бронирования с живым `DriveBookWidget.mount()`** → stats-strip → process
(road-timeline, 4 шага, scroll-driven car-marker) → instructors (3
карточки-плейсхолдеры) → testimonial (плейсхолдер) → cta-band → instructor-bar
("Ты инструктор? → /admin") → footer → mobile sticky tap-bar → FAB
(Telegram/WhatsApp/Viber).

**Баг найден и исправлен при вёрстке (не был бы пойман без раскладки в
браузере): `.nav-links`** — слайд-ин мобильное меню обязано быть DOM-siblings
у `<nav>`, а не вложено в `.nav-inner` — у `.nav` есть `backdrop-filter`,
который создаёт containing block для `position: fixed`-потомков, так что
вложенный drawer обрезался бы по рамке хедера вместо всего viewport. Из-за
этого тот же элемент нельзя было переиспользовать для десктопной инлайн-навигации
через один медиа-запрос (так было в референсе и в первой версии — desktop
ломался). Решение: два отдельных элемента — `.nav-links` (мобильный drawer,
fixed, sibling) и `.nav-links-desktop` (обычный inline, только `display`
переключается по media query).

**Embed-контекст виджета** — тот же паттерн, что в сессии 3, перенесён на
новый контейнер `.widget-frame`: `.db-root`/`.db-shell { min-height: auto }`,
`.db-foot-cta { position: sticky }`, `.db-nav-lang { display: none }` (у
лендинга свой RO/RU-переключатель в шапке, перемонтирует виджет через
`DriveBookWidget.mount()` заново — публичного API смены языка на лету нет).

**`api/app/main.py`**: добавлен `GET /robots.txt` — `Disallow` для известных
AI-краулеров (GPTBot, ClaudeBot, CCBot, Google-Extended, PerplexityBot,
Bytespider, anthropic-ai и т.д.), остальным `Allow: /`. Плюс
`<meta name="robots" content="noai, noimageai">` в обоих `landing/index*.html`.
Best-effort — не блокирует скрейперы, игнорирующие robots.txt.

**Известный гэп**: `admin/index.html` не тронут, там всё ещё amber `#F2A93B`
из сессии 3 — не совпадает с новым `#F26A0E`. Не критично (внутренний
инструмент), но стоит выровнять при следующей правке admin.

**Плейсхолдеры, не заполненные в сессии 4** (как и раньше в §Приоритет 3):
адрес/телефон/email в футере, соцсети (`href="#"`), FAB-ссылки
(t.me/wa.me/viber — заглушки), 3 карточки инструкторов и testimonial —
демо-контент, не реальные данные.

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
| `16e16d6` | навy+amber палитра везде; фикс require_admin (Bearer-сессии); форс-смена пароля + `/v1/auth/change-password`; supervisor через `.env`/`DRIVEBOOK_SUPERVISOR_*`; фиксы embed-контекста виджета (100dvh, position:fixed, двойной RO/RU); фикс `[object Object]` в admin; car-illustration sizing |
| *(этот коммит)* | сессия 4 — лендинг перерисован (Sky+Tangerine `landing/index.html` + Neutral+orange `landing/index-bsm.html`, общий `landing/landing.css`, разделённые токены `tokens-sky.css`/`tokens-bsm.css`); единый accent `#F26A0E` в обоих лендингах и `widget/widget.css`; `GET /robots.txt` + `noai`-мета; фикс containing-block бага в моб. навигации |

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
Актуально для **обоих** файлов — `landing/index.html` и `landing/index-bsm.html`
(один и тот же контент, правь в обоих или вынеси в общий partial):
- [ ] адрес/телефон/email в футере (сейчас `[str. Exemplu 1]`, `[+373 XX XXX XXX]`, `[contact@permispro.md]`)
- [ ] Facebook/Instagram/TikTok — реальные ссылки вместо `href="#"`
- [ ] Telegram/WhatsApp/Viber в плавающей FAB-кнопке — реальные `t.me/…`, `wa.me/…`, `viber://…`
- [ ] 3 карточки инструкторов (Andrei V./Maria C./Dumitru R.) и testimonial
      (Elena T.) — демо-данные, заменить на реальных людей
- [ ] `admin/index.html` всё ещё на старом amber `#F2A93B` — выровнять
      с `#F26A0E`, когда будет правка admin-панели (см. §0, §1.3)

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
# → http://127.0.0.1:8100/                       — лендинг, Sky+Tangerine (основной)
# → http://127.0.0.1:8100/landing/index-bsm.html  — тот же лендинг, Neutral+orange
# → http://127.0.0.1:8100/book                    — виджет бронирования отдельно
# → http://127.0.0.1:8100/admin                   — панель администратора
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
