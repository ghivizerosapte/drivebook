/**
 * DriveBook Widget v3.0 — BSM Mobile Edition
 * Chișinău only · RO/RU · Shadow DOM embed
 */
(function (global) {

  // ── i18n ────────────────────────────────────────────────────────────────
  const STR = {
    ro: {
      back: "Înapoi", exit: "Ieșire",
      gearbox: "Cutie de viteze",
      manual: "Manuală", automatic: "Automată",
      changeInstructor: "SCHIMBĂ INSTRUCTORUL",
      lessonTypeQ: "Ce tip de lecție dorești?",
      lesson1: "Vreau să învăț să conduc",
      lesson2: "Lecții de perfecționare / reîmprospătare",
      lesson3: "Am examenul în curând (max. 14 zile)",
      lessonHint: "Poți opta pentru cadou mai târziu.",
      titleBest: "Cele mai apropiate 3 locuri libere",
      titlePick: "Alege instructorul",
      titleSlots: "Alege ora",
      titleContact: "Confirmă rezervarea",
      titleDone: "Ești programat!",
      name: "Nume", phone: "Telefon",
      pickup: "De unde doriți să fiți ridicat?",
      pickupPlaceholder: "Adresă sau reper…",
      book: "REZERVĂ ACUM",
      continueBtn: "CONTINUĂ",
      again: "PROGRAMARE NOUĂ",
      waitlist: "LISTA DE AȘTEPTARE",
      loading: "Se încarcă…",
      empty: "Nicio oră disponibilă",
      noSlots: "Nu sunt locuri libere în această zi",
      allInstructors: "TOȚI INSTRUCTORII",
      lessonDetails: "Detalii lecție",
      instructor: "Instructor",
      zone: "Sector",
      searchPlaceholder: "Caută instructor…",
      phoneInvalid: "Număr de mobil invalid. Format: +373 6X XXX XXX sau 7X XXX XXX.",
      formError: "Ceva nu a funcționat. Vă rugăm să reîncercați.",
      termsLabel: "Am citit și accept ",
      termsLink: "termenii și condițiile",
      termsRequired: "Trebuie să acceptați termenii pentru a continua.",
      termsText: "Rezervarea online constituie o confirmare a intenției dvs. de a participa la lecție. Școala de șoferi poate anula sau reprograma lecția cu o notificare prealabilă de cel puțin 2 ore. Plata se efectuează direct instructorului. Anularea gratuită este posibilă cu cel puțin 24 de ore înainte de lecție. Datele dvs. personale (nume, telefon) sunt prelucrate exclusiv în scopul organizării cursului, în conformitate cu Legea nr. 133/2011 privind protecția datelor cu caracter personal a Republicii Moldova, și nu vor fi transmise terților fără consimțământul dvs.",
      districts: {
        "Botanica": "Botanica", "Centru": "Centru",
        "Buiucani": "Buiucani", "Rîșcani": "Rîșcani", "Ciocana": "Ciocana",
      },
    },
    ru: {
      back: "Назад", exit: "Выход",
      gearbox: "Коробка передач",
      manual: "Механика", automatic: "Автомат",
      changeInstructor: "СМЕНИТЬ ИНСТРУКТОРА",
      lessonTypeQ: "Какой урок вас интересует?",
      lesson1: "Хочу научиться водить",
      lesson2: "Уроки совершенствования / повторения",
      lesson3: "У меня экзамен в ближайшее время (до 14 дней)",
      lessonHint: "Подарочный вариант можно выбрать позже.",
      titleBest: "3 ближайших свободных места",
      titlePick: "Выбери инструктора",
      titleSlots: "Выбери время",
      titleContact: "Подтверди запись",
      titleDone: "Вы записаны!",
      name: "Имя", phone: "Телефон",
      pickup: "Откуда вас удобнее забрать?",
      pickupPlaceholder: "Адрес или ориентир…",
      book: "ЗАПИСАТЬСЯ",
      continueBtn: "ПРОДОЛЖИТЬ",
      again: "НОВАЯ ЗАПИСЬ",
      waitlist: "ЛИСТ ОЖИДАНИЯ",
      loading: "Загрузка…",
      empty: "Нет свободных мест",
      noSlots: "Нет мест в этот день",
      allInstructors: "ВСЕ ИНСТРУКТОРЫ",
      lessonDetails: "Детали урока",
      instructor: "Инструктор",
      zone: "Район",
      searchPlaceholder: "Поиск инструктора…",
      phoneInvalid: "Неверный мобильный номер. Формат: +373 6X XXX XXX или 7X XXX XXX.",
      formError: "Что-то пошло не так. Пожалуйста, попробуйте снова.",
      termsLabel: "Я прочитал и принимаю ",
      termsLink: "условия и положения",
      termsRequired: "Необходимо принять условия для продолжения.",
      termsText: "Онлайн-бронирование является подтверждением вашего намерения посетить занятие. Автошкола вправе отменить или перенести занятие с уведомлением не менее чем за 2 часа. Оплата производится напрямую инструктору. Бесплатная отмена возможна не менее чем за 24 часа до занятия. Ваши персональные данные (имя, телефон) обрабатываются исключительно в целях организации курса, в соответствии с Законом № 133/2011 о защите персональных данных Республики Молдова, и не будут переданы третьим лицам без вашего согласия.",
      districts: {
        "Botanica": "Ботаника", "Centru": "Центр",
        "Buiucani": "Буюканы", "Rîșcani": "Рышкановка", "Ciocana": "Чеканы",
      },
    },
  };
  const t = (lang, key) => (STR[lang] || STR.ro)[key] ?? STR.ro[key] ?? key;
  const dist = (lang, d) => (STR[lang]?.districts || STR.ro.districts)[d] || d;

  // ── Helpers ──────────────────────────────────────────────────────────────
  const AVATAR_COLORS = [
    "#F07C00","#E05A3A","#3A8FBF","#5B7FA6","#6B8E5E","#8B5E8E","#5E8E7A",
  ];
  function avatarColor(name) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
    return AVATAR_COLORS[h % AVATAR_COLORS.length];
  }
  function initials(name) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }
  function avatar(name, small) {
    const cls = small ? "db-avatar db-avatar-sm" : "db-avatar";
    return `<span class="${cls}" style="background:${avatarColor(name)}">${initials(name)}</span>`;
  }

  // Drop last slot of each calendar day (req #1)
  function filterLastSlot(slots) {
    const byDay = {};
    for (const s of slots) {
      const day = s.starts_at.slice(0, 10);
      if (!byDay[day]) byDay[day] = [];
      byDay[day].push(s);
    }
    const kept = new Set();
    for (const day of Object.keys(byDay)) {
      const sorted = byDay[day].slice().sort((a, b) => a.starts_at.localeCompare(b.starts_at));
      sorted.slice(0, -1).forEach(s => kept.add(s.id));
    }
    return slots.filter(s => kept.has(s.id));
  }

  // Format time range: "09:30 — 11:00"
  function fmtTime(starts, ends, lang) {
    const loc = lang === "ru" ? "ru-RU" : "ro-RO";
    const hm = d => new Date(d).toLocaleTimeString(loc, { hour: "2-digit", minute: "2-digit" });
    const end = ends || new Date(new Date(starts).getTime() + 90 * 60000).toISOString();
    return `${hm(starts)} — ${hm(end)}`;
  }

  // Format full date label: "Vin, 25 Iun"
  function fmtDate(iso, lang) {
    const loc = lang === "ru" ? "ru-RU" : "ro-RO";
    return new Date(iso).toLocaleDateString(loc, { weekday: "short", day: "numeric", month: "short" });
  }

  // Day key "2026-07-25"
  const dayKey = iso => iso.slice(0, 10);

  // ── Moldovan mobile mask (+373 6X/7X XXX XXX) ─────────────────────────────
  // Extract the 8-digit national part from any pasted/typed form:
  //   069123456 · 373 69 123 456 · +37369123456 · 69123456
  function phoneNational(raw) {
    let d = (raw || "").replace(/\D/g, "");
    if (d.startsWith("373")) d = d.slice(3);   // country code
    if (d.startsWith("0")) d = d.slice(1);     // trunk prefix
    return d.slice(0, 8);                       // never more than 8 national digits
  }
  // Group national digits as "69 123 456"
  function phoneFormat(nat) {
    let out = nat.slice(0, 2);
    if (nat.length > 2) out += " " + nat.slice(2, 5);
    if (nat.length > 5) out += " " + nat.slice(5, 8);
    return out;
  }
  // Valid iff exactly 8 digits and first is 6 or 7
  function phoneValid(nat) {
    return /^[67]\d{7}$/.test(nat);
  }

  // Clock SVG icon
  const CLOCK_SVG = `<svg class="db-slot-icon" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
    <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>
  </svg>`;

  // ── API ──────────────────────────────────────────────────────────────────
  async function api(base, path, opts) {
    const res = await fetch(base + path, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      let msg;
      if (typeof data.detail === "string") {
        msg = data.detail;
      } else if (Array.isArray(data.detail) && data.detail.length) {
        // Pydantic validation errors: [{loc, msg, type}, ...]
        msg = data.detail[0].msg || `HTTP ${res.status}`;
      } else {
        msg = data.detail?.message || `HTTP ${res.status}`;
      }
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  // ── Mount ────────────────────────────────────────────────────────────────
  function mount(root, options) {
    const opts = options || {};
    const base = opts.apiBase || "";

    const state = {
      lang: opts.lang || "ro",
      source: opts.source || "widget",
      lessonType: "standard",  // "standard" | "exam"
      transmission: "",        // "" | "manual" | "automatic"
      instructor: null,        // selected instructor object
      slot: null,              // selected slot object
      fromInstructor: false,   // true when path: pick instructor → slot → contact
      calDays: [],             // sorted day keys for the slot picker
      calDayIdx: 0,            // first visible day index in scroller
      calSlots: {},            // { dayKey: [slot, …] }
      changeOpen: false,       // "change instructor" dropdown open
      altInstructors: [],      // fetched list for change dropdown
    };

    // ── Shell ──────────────────────────────────────────────────────────────
    root.innerHTML = `
      <div class="db-root">
        <div class="db-shell">
          <div class="db-progress" data-progress></div>
          <div class="db-nav">
            <button class="db-nav-back" data-back type="button">← <span data-back-label></span></button>
            <div class="db-nav-lang">
              <button type="button" data-lang="ro">RO</button>
              <button type="button" data-lang="ru">RU</button>
            </div>
            <button class="db-nav-exit" data-exit type="button">✕</button>
          </div>
          <div class="db-body" data-body></div>
          <div class="db-foot-cta" data-foot></div>
        </div>
      </div>`;

    const body   = root.querySelector("[data-body]");
    const foot   = root.querySelector("[data-foot]");
    const prog   = root.querySelector("[data-progress]");
    const $      = s => root.querySelector(s);

    // ── Chrome helpers ─────────────────────────────────────────────────────
    function setProgress(step) {         // step 1-5
      prog.innerHTML = Array.from({ length: 5 }, (_, i) =>
        `<div class="db-progress-seg ${i < step ? "on" : ""}"></div>`
      ).join("");
    }

    function setNav(backFn, showBack) {
      const backBtn   = $("[data-back]");
      const backLabel = $("[data-back-label]");
      backLabel.textContent = t(state.lang, "back");
      backBtn.style.visibility = showBack ? "visible" : "hidden";
      backBtn.onclick = backFn || null;
    }

    function setFootCta(label, onClick, disabled) {
      foot.innerHTML = `<button class="db-btn-primary" type="button">${label}</button>`;
      const btn = foot.querySelector("button");
      if (disabled) btn.disabled = true;
      btn.onclick = onClick;
    }

    function clearFoot() { foot.innerHTML = ""; }

    function applyLang() {
      root.querySelectorAll("[data-lang]").forEach(b => {
        b.classList.toggle("active", b.dataset.lang === state.lang);
      });
      $("[data-back-label]").textContent = t(state.lang, "back");
      $("[data-exit]").title = t(state.lang, "exit");
    }

    root.querySelectorAll("[data-lang]").forEach(b => {
      b.onclick = () => { state.lang = b.dataset.lang; applyLang(); rerender(); };
    });

    $("[data-exit]").onclick = () => { state.slot = null; state.instructor = null; renderLessonType(); };

    let currentView = "lessonType";
    function rerender() {
      if (currentView === "lessonType")  renderLessonType();
      else if (currentView === "best")   renderBest();
      else if (currentView === "inst")   renderInstructors();
      else if (currentView === "slots")  renderSlotPicker();
      else if (currentView === "contact") renderContact();
    }

    // ── Gearbox tabs ──────────────────────────────────────────────────────
    function gearboxTabs() {
      const L = state.lang;
      return `
        <p class="db-tab-label">${t(L, "gearbox")}</p>
        <div class="db-tabs">
          <button class="db-tab ${state.transmission === "" ? "active" : ""}"
            type="button" data-tx="">Toate</button>
          <button class="db-tab ${state.transmission === "manual" ? "active" : ""}"
            type="button" data-tx="manual">${t(L, "manual")}</button>
          <button class="db-tab ${state.transmission === "automatic" ? "active" : ""}"
            type="button" data-tx="automatic">${t(L, "automatic")}</button>
        </div>`;
    }

    function bindTabs() {
      body.querySelectorAll("[data-tx]").forEach(btn => {
        btn.onclick = () => {
          state.transmission = btn.dataset.tx;
          rerender();
        };
      });
    }

    // ── VIEW: Lesson type picker (first screen) ────────────────────────────
    function renderLessonType() {
      currentView = "lessonType";
      const L = state.lang;
      setProgress(1);
      setNav(null, false);

      const lessons = [
        { key: "lesson1", type: "standard" },
        { key: "lesson2", type: "standard" },
        { key: "lesson3", type: "exam"     },
      ];

      body.innerHTML = `
        <p class="db-heading">${t(L, "lessonTypeQ")}</p>
        <div class="db-slot-list" style="margin-bottom:20px">
          ${lessons.map(l => `
            <button class="db-slot-row${state.lessonType === l.type && l.key === _activeLessonKey() ? " active" : ""}"
              type="button" data-lkey="${l.key}" data-ltype="${l.type}">
              <div class="db-slot-time" style="font-size:15px;font-weight:500">${t(L, l.key)}</div>
            </button>`).join("")}
        </div>
        `;

      // track which card is selected
      let selectedKey = lessons[0].key;
      state.lessonType = lessons[0].type;
      body.querySelectorAll("[data-lkey]").forEach(btn => {
        if (btn.dataset.lkey === selectedKey) btn.classList.add("active");
        btn.onclick = () => {
          selectedKey = btn.dataset.lkey;
          state.lessonType = btn.dataset.ltype;
          body.querySelectorAll("[data-lkey]").forEach(b => b.classList.remove("active"));
          btn.classList.add("active");
        };
      });

      setFootCta(t(L, "continueBtn"), () => renderBest());
    }

    function _activeLessonKey() { return "lesson1"; } // default selection marker

    // ── VIEW: Best (3 closest slots) ──────────────────────────────────────
    async function renderBest() {
      currentView = "best";
      const L = state.lang;
      setProgress(2);
      setNav(() => renderLessonType(), true);
      body.innerHTML = `
        ${gearboxTabs()}
        <p class="db-title">${t(L, "titleBest")}</p>
        <div class="db-slot-list" data-list>
          <div class="db-loading">${t(L, "loading")}</div>
        </div>`;
      bindTabs();

      const list = body.querySelector("[data-list]");
      try {
        // fetch extra, filter last-of-day, take 3 soonest
        const p = new URLSearchParams({ limit: "10" });
        if (state.transmission) p.set("transmission", state.transmission);
        const data = await api(base, `/v1/slots/best?${p}`);
        const items = filterLastSlot(data.items).slice(0, 3);
        if (!items.length) {
          list.innerHTML = `<div class="db-empty-state">${t(L, "empty")}</div>`;
          foot.innerHTML = `<button class="db-btn-ghost" type="button" data-all>${t(L, "allInstructors")}</button>`;
          foot.querySelector("[data-all]").onclick = () => renderInstructors();
          return;
        }
        list.innerHTML = items.map(s => `
          <button class="db-slot-row" type="button" data-sid="${s.id}">
            ${CLOCK_SVG}
            <div>
              <div class="db-slot-time">${fmtTime(s.starts_at, s.ends_at, L)}</div>
              <div class="db-slot-sub">${fmtDate(s.starts_at, L)} · ${s.instructor_name} · ${dist(L, s.district)}</div>
            </div>
          </button>`).join("");

        list.querySelectorAll("[data-sid]").forEach(btn => {
          btn.onclick = () => {
            const item = items.find(x => x.id === Number(btn.dataset.sid));
            state.slot = item;
            state.instructor = { id: item.instructor_id, name: item.instructor_name, district: item.district };
            state.fromInstructor = false;
            renderContact();
          };
        });

        // secondary CTA in footer
        foot.innerHTML = `<button class="db-btn-ghost" type="button" data-all>${t(L, "allInstructors")}</button>`;
        foot.querySelector("[data-all]").onclick = () => renderInstructors();

      } catch (e) {
        list.innerHTML = `<div class="db-error">${e.message}</div>`;
      }
    }

    // ── VIEW: Instructor picker ────────────────────────────────────────────
    async function renderInstructors() {
      currentView = "inst";
      const L = state.lang;
      setProgress(3);
      setNav(() => renderBest(), true);
      clearFoot();

      body.innerHTML = `
        ${gearboxTabs()}
        <p class="db-title">${t(L, "titlePick")}</p>
        <input class="db-search" type="search" placeholder="${t(L, "searchPlaceholder")}" data-q />
        <div class="db-inst-list" data-list>
          <div class="db-loading">${t(L, "loading")}</div>
        </div>`;
      bindTabs();

      const list = body.querySelector("[data-list]");
      const qInput = body.querySelector("[data-q]");
      let timer;
      qInput.oninput = () => { clearTimeout(timer); timer = setTimeout(load, 220); };

      async function load() {
        list.innerHTML = `<div class="db-loading">${t(L, "loading")}</div>`;
        const p = new URLSearchParams({ limit: "30" });
        if (qInput.value.trim()) p.set("q", qInput.value.trim());
        if (state.transmission) p.set("transmission", state.transmission);
        try {
          const data = await api(base, `/v1/instructors?${p}`);
          if (!data.items.length) {
            list.innerHTML = `<div class="db-empty-state">${t(L, "empty")}</div>`;
            return;
          }
          list.innerHTML = data.items.map(i => `
            <button class="db-inst-row" type="button" data-id="${i.id}">
              ${avatar(i.name)}
              <div>
                <div class="db-inst-name">${i.name}</div>
                <div class="db-inst-meta">${dist(L, i.district)} · ${i.car} · ${Number(i.rating).toFixed(1)}★</div>
              </div>
            </button>`).join("");
          list.querySelectorAll("[data-id]").forEach(btn => {
            btn.onclick = () => {
              state.instructor = data.items.find(x => x.id === Number(btn.dataset.id));
              state.fromInstructor = true;
              renderSlotPicker();
            };
          });
        } catch (e) {
          list.innerHTML = `<div class="db-error">${e.message}</div>`;
        }
      }
      await load();
    }

    // ── VIEW: Slot picker (instructor calendar) ────────────────────────────
    async function renderSlotPicker() {
      currentView = "slots";
      const L = state.lang;
      setProgress(4);
      setNav(() => renderInstructors(), true);
      clearFoot();

      body.innerHTML = `
        <div class="db-instructor-row">
          ${avatar(state.instructor.name)}
          <div>
            <div class="db-instructor-name">${state.instructor.name}</div>
            <div class="db-instructor-sub">${dist(L, state.instructor.district || "")}</div>
          </div>
        </div>
        <button class="db-change-link" type="button" data-change>
          ⇄ ${t(L, "changeInstructor")}
        </button>
        <div data-change-list style="display:none"></div>
        <p class="db-title">${t(L, "titleSlots")}</p>
        <div data-cal>
          <div class="db-loading">${t(L, "loading")}</div>
        </div>`;

      // "Change instructor" toggle
      body.querySelector("[data-change]").onclick = async () => {
        const drawer = body.querySelector("[data-change-list]");
        state.changeOpen = !state.changeOpen;
        drawer.style.display = state.changeOpen ? "block" : "none";
        if (state.changeOpen && !state.altInstructors.length) {
          drawer.innerHTML = `<div class="db-loading">${t(L, "loading")}</div>`;
          try {
            const p = new URLSearchParams({ limit: "10" });
            if (state.transmission) p.set("transmission", state.transmission);
            const data = await api(base, `/v1/instructors?${p}`);
            state.altInstructors = data.items.filter(i => i.id !== state.instructor.id).slice(0, 6);
          } catch (_) { state.altInstructors = []; }
        }
        if (state.changeOpen) {
          drawer.innerHTML = `<div class="db-change-list">
            ${state.altInstructors.map(i => `
              <button class="db-change-item" type="button" data-iid="${i.id}">
                ${avatar(i.name, true)}
                <span>${i.name}</span>
              </button>`).join("")}
          </div>`;
          drawer.querySelectorAll("[data-iid]").forEach(btn => {
            btn.onclick = () => {
              state.instructor = state.altInstructors.find(x => x.id === Number(btn.dataset.iid));
              state.altInstructors = [];
              state.changeOpen = false;
              renderSlotPicker();
            };
          });
        }
      };

      // Load calendar
      const calEl = body.querySelector("[data-cal]");
      try {
        const cal = await api(base, `/v1/instructors/${state.instructor.id}/calendar`);
        const rawDays = Object.keys(cal.days || {}).sort();
        if (!rawDays.length) {
          calEl.innerHTML = `<div class="db-empty-state">${t(L, "empty")}</div>`;
          foot.innerHTML = `<button class="db-btn-ghost" type="button" data-wl>${t(L, "waitlist")}</button>`;
          foot.querySelector("[data-wl]").onclick = () => joinWaitlist(state.instructor.id);
          return;
        }

        // Filter: drop last slot per day, rebuild days
        state.calSlots = {};
        for (const day of rawDays) {
          const free = cal.days[day].filter(s => s.free);
          const kept = filterLastSlot(free);
          if (kept.length) state.calSlots[day] = kept;
        }
        state.calDays = Object.keys(state.calSlots).sort();
        if (!state.calDays.length) {
          calEl.innerHTML = `<div class="db-empty-state">${t(L, "empty")}</div>`;
          return;
        }
        state.calDayIdx = 0;
        renderDateScroller(calEl, L);
      } catch (e) {
        calEl.innerHTML = `<div class="db-error">${e.message}</div>`;
      }
    }

    function renderDateScroller(calEl, L) {
      const days  = state.calDays;
      const idx   = state.calDayIdx;
      const vis   = days.slice(idx, idx + 3);   // 3 visible day cards
      const selDay = vis[0];                     // first visible = selected day

      const dayCard = (day, active) => {
        const d = new Date(day + "T12:00:00");
        const dow = d.toLocaleDateString(L === "ru" ? "ru-RU" : "ro-RO", { weekday: "short" }).toUpperCase().replace(".", "");
        const num = d.getDate();
        const mon = d.toLocaleDateString(L === "ru" ? "ru-RU" : "ro-RO", { month: "short" }).toUpperCase().replace(".", "");
        return `<button class="db-date-card${active ? " active" : ""}" type="button" data-day="${day}">
          <span class="db-date-dow">${dow}</span>
          <span class="db-date-day">${num}</span>
          <span class="db-date-mon">${mon}</span>
        </button>`;
      };

      calEl.innerHTML = `
        <div class="db-date-nav">
          <button class="db-date-arrow" type="button" data-prev ${idx === 0 ? "disabled" : ""}>‹</button>
          <div class="db-date-scroll">
            ${vis.map((d, i) => dayCard(d, i === 0)).join("")}
          </div>
          <button class="db-date-arrow" type="button" data-next ${idx + 3 >= days.length ? "disabled" : ""}>›</button>
        </div>
        <div class="db-slot-list" data-slots></div>`;

      calEl.querySelector("[data-prev]")?.addEventListener("click", () => {
        state.calDayIdx = Math.max(0, idx - 3);
        renderDateScroller(calEl, L);
      });
      calEl.querySelector("[data-next]")?.addEventListener("click", () => {
        state.calDayIdx = Math.min(days.length - 1, idx + 3);
        renderDateScroller(calEl, L);
      });

      calEl.querySelectorAll("[data-day]").forEach((btn, i) => {
        btn.onclick = () => {
          state.calDayIdx = days.indexOf(btn.dataset.day);
          renderDateScroller(calEl, L);
        };
      });

      renderDaySlots(calEl.querySelector("[data-slots]"), selDay, L);

      // Footer CTA disabled until slot selected
      setFootCta(t(L, "continueBtn"), () => {
        if (state.slot) renderContact();
      }, !state.slot);
    }

    function renderDaySlots(slotsEl, day, L) {
      const slots = state.calSlots[day] || [];
      if (!slots.length) {
        slotsEl.innerHTML = `<div class="db-empty-state">${t(L, "noSlots")}</div>`;
        return;
      }
      slotsEl.innerHTML = slots.map(s => {
        const active = state.slot?.id === s.id;
        return `<button class="db-slot-row${active ? " active" : ""}" type="button" data-slotid="${s.id}">
          ${CLOCK_SVG}
          <div>
            <div class="db-slot-time">${fmtTime(s.starts_at, s.ends_at, L)}</div>
          </div>
        </button>`;
      }).join("");

      slotsEl.querySelectorAll("[data-slotid]").forEach(btn => {
        btn.onclick = () => {
          const s = slots.find(x => x.id === Number(btn.dataset.slotid));
          state.slot = s;
          slotsEl.querySelectorAll(".db-slot-row").forEach(b => b.classList.remove("active"));
          btn.classList.add("active");
          // enable continue
          const ctaBtn = foot.querySelector("button");
          if (ctaBtn) ctaBtn.disabled = false;
        };
      });
    }

    // ── VIEW: Contact form ─────────────────────────────────────────────────
    function renderContact() {
      currentView = "contact";
      const L = state.lang;
      // Min-fill-time anti-bot: remember when this screen opened.
      state.contactOpenedAt = Date.now();
      setProgress(5);
      setNav(() => state.fromInstructor ? renderSlotPicker() : renderBest(), true);
      clearFoot();

      const s = state.slot;
      const inst = state.instructor;

      body.innerHTML = `
        <p class="db-title">${t(L, "titleContact")}</p>
        <div class="db-summary">
          <div class="db-summary-row">
            ${CLOCK_SVG}
            <div>
              <div>${fmtTime(s.starts_at, s.ends_at, L)}</div>
              <div class="db-summary-label">${fmtDate(s.starts_at, L)}</div>
            </div>
          </div>
          <div class="db-summary-row">
            ${avatar(inst.name, true)}
            <div>
              <div>${inst.name}</div>
              <div class="db-summary-label">${dist(L, inst.district || "")}</div>
            </div>
          </div>
        </div>
        <form class="db-form" data-form>
          <div class="db-field">
            <label for="db-name">${t(L, "name")}</label>
            <input id="db-name" name="student_name" required minlength="2" autocomplete="name" />
          </div>
          <div class="db-field">
            <label for="db-phone">${t(L, "phone")}</label>
            <div class="db-phone-wrap">
              <span class="db-phone-prefix">+373</span>
              <input id="db-phone" name="student_phone_national" required type="tel"
                inputmode="numeric" placeholder="6X XXX XXX"
                autocomplete="tel-national" data-phone />
            </div>
          </div>
          <div class="db-field">
            <label for="db-pickup">${t(L, "pickup")}</label>
            <input id="db-pickup" name="pickup" placeholder="${t(L, "pickupPlaceholder")}"
              autocomplete="street-address" />
          </div>
          <input type="text" name="contact_notes_x" data-hp class="db-hp"
            tabindex="-1" autocomplete="off" aria-hidden="true" />
          <div class="db-field db-field-terms">
            <div class="db-terms-body" data-terms-body style="display:none">
              ${t(L, "termsText")}
            </div>
            <label class="db-terms-label">
              <input type="checkbox" name="terms" data-terms />
              <span>${t(L, "termsLabel")}<a href="#" class="db-terms-link" data-terms-toggle>${t(L, "termsLink")}</a></span>
            </label>
          </div>
          <div data-err></div>
        </form>`;

      // Phone mask: live-format + normalize pasted input, cap at 8 national digits
      const phoneEl = body.querySelector("[data-phone]");
      phoneEl.addEventListener("input", () => {
        // Preserve the caret: full-value rewrite would otherwise jump it to the
        // end, breaking mid-string typing/deleting. Count digits left of the
        // caret, reformat, then land the caret after that many digits.
        const caret = phoneEl.selectionStart || 0;
        const digitsLeft = (phoneEl.value.slice(0, caret).match(/\d/g) || []).length;
        phoneEl.value = phoneFormat(phoneNational(phoneEl.value));
        let pos = 0, seen = 0;
        while (pos < phoneEl.value.length && seen < digitsLeft) {
          if (/\d/.test(phoneEl.value[pos])) seen++;
          pos++;
        }
        phoneEl.setSelectionRange(pos, pos);
      });

      // Terms toggle
      body.querySelector("[data-terms-toggle]").addEventListener("click", e => {
        e.preventDefault();
        const box = body.querySelector("[data-terms-body]");
        box.style.display = box.style.display === "none" ? "block" : "none";
      });

      // Foot CTA: disabled until T&C checked
      foot.innerHTML = `<button class="db-btn-primary" type="button" data-submit disabled>${t(L, "book")}</button>`;
      const submitBtn = foot.querySelector("[data-submit]");

      body.querySelector("[data-terms]").addEventListener("change", e => {
        submitBtn.disabled = !e.target.checked;
      });

      submitBtn.onclick = async () => {
        const form = body.querySelector("[data-form]");
        const errEl = body.querySelector("[data-err]");
        errEl.innerHTML = "";

        // Anti-bot: honeypot filled OR form submitted implausibly fast → refuse
        // with a neutral message (don't hint at the trap).
        const hp = form.querySelector("[data-hp]");
        const tooFast = Date.now() - (state.contactOpenedAt || 0) < 3000;
        if ((hp && hp.value) || tooFast) {
          errEl.innerHTML = `<div class="db-error">${t(L, "formError")}</div>`;
          return;
        }

        // Moldovan mobile validation: exactly 8 national digits, first 6 or 7
        const national = phoneNational(form.querySelector("[data-phone]").value);
        if (!phoneValid(national)) {
          errEl.innerHTML = `<div class="db-error">${t(L, "phoneInvalid")}</div>`;
          return;
        }
        const phoneVal = "+373" + national;

        if (!form.reportValidity()) return;

        const fd = new FormData(form);
        submitBtn.disabled = true;
        try {
          const res = await api(base, "/v1/bookings", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Idempotency-Key": `w-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            },
            body: JSON.stringify({
              slot_id: s.id,
              student_name: fd.get("student_name"),
              student_phone: phoneVal,
              contact_notes_x: fd.get("contact_notes_x") || "",
              notes: fd.get("pickup") || null,
              lesson_type: state.lessonType,
              source: state.source,
              lang: state.lang,
            }),
          });
          renderDone(res.booking, fd.get("student_name"));
        } catch (e) {
          errEl.innerHTML = `<div class="db-error">${e.message}</div>`;
          submitBtn.disabled = false;
        }
      };
    }

    // ── VIEW: Done / Congratulations ───────────────────────────────────────
    function renderDone(b, studentName) {
      currentView = "done";
      const L = state.lang;
      setProgress(5);
      setNav(null, false);

      const firstName = (studentName || b.student_name || "").split(" ")[0];
      const d = new Date(b.starts_at);
      const dayNum = d.getDate();

      body.innerHTML = `
        <div class="db-congrats-wrap">
          <div class="db-congrats-illus">🎉</div>
          <div class="db-congrats-title">
            ${L === "ru" ? "Поздравляем" : "Felicitări"} ${firstName}!<br>
            ${t(L, "titleDone")}
          </div>
          <div class="db-congrats-sub">#${b.id}</div>
        </div>
        <div class="db-details-card">
          <div class="db-details-title">${t(L, "lessonDetails")}</div>
          <div class="db-details-row">
            <span class="db-avatar db-avatar-sm" style="background:${AVATAR_COLORS[2]};font-size:13px;font-weight:700">${dayNum}</span>
            <div class="db-details-row-text">
              <span class="db-details-main">${fmtTime(b.starts_at, b.ends_at, L)}</span>
              <span class="db-details-sub">${fmtDate(b.starts_at, L)}</span>
            </div>
          </div>
          <div class="db-details-row">
            ${avatar(b.instructor_name || state.instructor?.name || "–", true)}
            <div class="db-details-row-text">
              <span class="db-details-main">${b.instructor_name || state.instructor?.name || "–"}</span>
              <span class="db-details-sub">${t(L, "instructor")}</span>
            </div>
          </div>
          <div class="db-details-row">
            <span class="db-avatar db-avatar-sm" style="background:#888">📍</span>
            <div class="db-details-row-text">
              <span class="db-details-main">${dist(L, b.district || state.instructor?.district || "")}</span>
              <span class="db-details-sub">${t(L, "zone")}</span>
            </div>
          </div>
        </div>`;

      foot.innerHTML = `<button class="db-btn-ghost" type="button" data-again>${t(L, "again")}</button>`;
      foot.querySelector("[data-again]").onclick = () => {
        state.slot = null; state.instructor = null;
        state.fromInstructor = false; state.changeOpen = false;
        state.altInstructors = []; state.calDays = []; state.calSlots = {};
        state.lessonType = "standard";
        renderLessonType();
      };
    }

    // ── Waitlist (prompt fallback) ─────────────────────────────────────────
    async function joinWaitlist(instructorId) {
      const name  = prompt(t(state.lang, "name"));
      const phone = prompt(t(state.lang, "phone"));
      if (!name || !phone) return;
      try {
        await api(base, "/v1/waitlist", {
          method: "POST",
          body: JSON.stringify({
            student_name: name, student_phone: phone,
            instructor_id: instructorId || null,
            lang: state.lang, source: state.source,
          }),
        });
      } catch (_) {}
    }

    // ── Boot ───────────────────────────────────────────────────────────────
    applyLang();
    renderLessonType();
  }

  global.DriveBookWidget = { mount };
})(typeof window !== "undefined" ? window : globalThis);
