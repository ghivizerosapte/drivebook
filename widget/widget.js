/**
 * DriveBook booking widget core.
 * Used by hosted page and Shadow DOM embed.
 */
(function (global) {
  const STR = {
    ro: {
      brand: "DriveBook",
      city: "Chișinău",
      titleGear: "Alege cutia de viteze",
      titleInstructor: "Alege instructorul",
      titleSlot: "Alege ora",
      titleContact: "Date de contact",
      titleDone: "Ești programat!",
      any: "Oricare",
      manual: "Manuală",
      automatic: "Automată",
      search: "Caută după nume / sector",
      book: "Rezervă lecția",
      name: "Nume",
      phone: "Telefon",
      email: "Email (opțional)",
      notes: "Comentariu",
      lesson: "Tip lecție",
      again: "Programare nouă",
      empty: "Nimic găsit",
      loading: "Se încarcă…",
      step1: "1. Cutie",
      step2: "2. Instructor",
      step3: "3. Oră",
      step4: "4. Contact",
      badge: "programare online",
      exp: "ani exp.",
      rating: "rating",
    },
    ru: {
      brand: "DriveBook",
      city: "Кишинёв",
      titleGear: "Выберите КПП",
      titleInstructor: "Выберите инструктора",
      titleSlot: "Выберите время",
      titleContact: "Контакты",
      titleDone: "Вы записаны!",
      any: "Любая",
      manual: "Механика",
      automatic: "Автомат",
      search: "Поиск по имени / району",
      book: "Записаться",
      name: "Имя",
      phone: "Телефон",
      email: "Email (необязательно)",
      notes: "Комментарий",
      lesson: "Тип урока",
      again: "Новая запись",
      empty: "Ничего не найдено",
      loading: "Загрузка…",
      step1: "1. КПП",
      step2: "2. Инструктор",
      step3: "3. Время",
      step4: "4. Контакт",
      badge: "онлайн-запись",
      exp: "лет опыта",
      rating: "рейтинг",
    },
  };

  function t(lang, key) {
    return (STR[lang] || STR.ro)[key] || STR.ro[key] || key;
  }

  function fmtDate(iso, lang) {
    const d = new Date(iso);
    return d.toLocaleString(lang === "ru" ? "ru-RU" : "ro-RO", {
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  async function api(base, path, opts) {
    const res = await fetch(base + path, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.detail || data.message || `HTTP ${res.status}`;
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return data;
  }

  function mount(root, options) {
    const opts = options || {};
    const base = opts.apiBase || "";
    const state = {
      lang: opts.lang || "ro",
      source: opts.source || "widget",
      step: 1,
      transmission: null,
      instructor: null,
      slot: null,
      meta: null,
    };

    // inject styles if document mode; shadow host should inject separately
    const cssHref = opts.cssHref || "/widget/widget.css";

    root.innerHTML = `
      <div class="db-root">
        <div class="db-shell">
          <div class="db-top">
            <div class="db-brand"><span>Drive</span>Book · <small style="font-weight:600;color:#6c757d" data-city></small></div>
            <div class="db-badge" data-badge></div>
          </div>
          <div class="db-lang">
            <button type="button" data-set-lang="ro">RO</button>
            <button type="button" data-set-lang="ru">RU</button>
          </div>
          <div class="db-steps">
            <button type="button" class="db-step" data-goto="1" data-s1></button>
            <button type="button" class="db-step" data-goto="2" data-s2></button>
            <button type="button" class="db-step" data-goto="3" data-s3></button>
            <button type="button" class="db-step" data-goto="4" data-s4></button>
          </div>
          <div class="db-body">
            <section data-panel="1"></section>
            <section data-panel="2" class="hidden"></section>
            <section data-panel="3" class="hidden"></section>
            <section data-panel="4" class="hidden"></section>
            <section data-panel="done" class="hidden"></section>
          </div>
          <div class="db-foot">Chișinău · DriveBook autonomous module</div>
        </div>
      </div>
    `;

    const $ = (sel) => root.querySelector(sel);
    const $$ = (sel) => [...root.querySelectorAll(sel)];

    function applyI18n() {
      const L = state.lang;
      $("[data-city]").textContent = t(L, "city");
      $("[data-badge]").textContent = t(L, "badge");
      $("[data-s1]").textContent = t(L, "step1");
      $("[data-s2]").textContent = t(L, "step2");
      $("[data-s3]").textContent = t(L, "step3");
      $("[data-s4]").textContent = t(L, "step4");
      $$(".db-lang button").forEach((b) => {
        b.classList.toggle("active", b.dataset.setLang === L);
      });
    }

    function setStep(n) {
      state.step = n;
      $$(".db-step").forEach((btn) => {
        const s = Number(btn.dataset.goto);
        btn.classList.toggle("active", s === n);
        btn.classList.toggle("done", typeof n === "number" && s < n);
      });
      $$("[data-panel]").forEach((p) => {
        const id = p.dataset.panel;
        if (n === "done") p.classList.toggle("hidden", id !== "done");
        else p.classList.toggle("hidden", id !== String(n));
      });
    }

    function renderGear() {
      const L = state.lang;
      const el = $('[data-panel="1"]');
      el.innerHTML = `
        <h1>${t(L, "titleGear")}</h1>
        <p class="db-lead">${t(L, "city")}</p>
        <div class="db-grid gears">
          <button class="db-card" data-tx="">
            <h3>${t(L, "any")}</h3>
            <p>—</p>
          </button>
          <button class="db-card" data-tx="manual">
            <h3>${t(L, "manual")}</h3>
            <p>MT</p>
          </button>
          <button class="db-card" data-tx="automatic">
            <h3>${t(L, "automatic")}</h3>
            <p>AT</p>
          </button>
        </div>
      `;
      el.querySelectorAll("[data-tx]").forEach((btn) => {
        btn.addEventListener("click", () => {
          state.transmission = btn.dataset.tx || null;
          setStep(2);
          loadInstructors();
        });
      });
    }

    async function loadInstructors() {
      const L = state.lang;
      const el = $('[data-panel="2"]');
      el.innerHTML = `<h1>${t(L, "titleInstructor")}</h1>
        <div class="db-filters"><input data-q type="search" placeholder="${t(L, "search")}" /></div>
        <div class="db-grid" data-list><div class="db-empty">${t(L, "loading")}</div></div>`;
      const list = el.querySelector("[data-list]");
      const qInput = el.querySelector("[data-q]");

      async function refresh() {
        list.innerHTML = `<div class="db-empty">${t(L, "loading")}</div>`;
        const params = new URLSearchParams({ limit: "40" });
        if (state.transmission) params.set("transmission", state.transmission);
        if (qInput.value.trim()) params.set("q", qInput.value.trim());
        try {
          const data = await api(base, `/v1/instructors?${params}`);
          if (!data.items.length) {
            list.innerHTML = `<div class="db-empty">${t(L, "empty")}</div>`;
            return;
          }
          list.innerHTML = data.items
            .map(
              (i) => `
            <button class="db-card" data-id="${i.id}">
              <h3>${i.name} · ${Number(i.rating).toFixed(1)}★</h3>
              <p>${i.district} · ${i.car} · ${i.transmission}</p>
              <div class="db-pills">
                <span class="db-pill">${i.experience_years} ${t(L, "exp")}</span>
                <span class="db-pill">${i.languages}</span>
              </div>
            </button>`
            )
            .join("");
          list.querySelectorAll("[data-id]").forEach((btn) => {
            btn.addEventListener("click", () => {
              state.instructor = data.items.find((x) => x.id === Number(btn.dataset.id));
              setStep(3);
              loadSlots();
            });
          });
        } catch (e) {
          list.innerHTML = `<div class="db-empty">${e.message}</div>`;
        }
      }

      let timer;
      qInput.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(refresh, 250);
      });
      await refresh();
    }

    async function loadSlots() {
      const L = state.lang;
      const el = $('[data-panel="3"]');
      el.innerHTML = `
        <h1>${t(L, "titleSlot")}</h1>
        <p class="db-lead">${state.instructor.name} · ${state.instructor.car}</p>
        <div class="db-slots" data-slots><div class="db-empty">${t(L, "loading")}</div></div>`;
      const box = el.querySelector("[data-slots]");
      try {
        const data = await api(base, `/v1/slots?instructor_id=${state.instructor.id}&limit=80`);
        if (!data.items.length) {
          box.innerHTML = `<div class="db-empty">${t(L, "empty")}</div>`;
          return;
        }
        box.innerHTML = data.items
          .map(
            (s) => `
          <button class="db-slot" data-id="${s.id}">
            <strong>${fmtDate(s.starts_at, L)}</strong>
            <span>${s.district}</span>
          </button>`
          )
          .join("");
        box.querySelectorAll("[data-id]").forEach((btn) => {
          btn.addEventListener("click", () => {
            state.slot = data.items.find((x) => x.id === Number(btn.dataset.id));
            setStep(4);
            renderContact();
          });
        });
      } catch (e) {
        box.innerHTML = `<div class="db-empty">${e.message}</div>`;
      }
    }

    function renderContact() {
      const L = state.lang;
      const el = $('[data-panel="4"]');
      const types = (state.meta && state.meta.lesson_types) || [
        { id: "standard", title_ro: "60 min", title_ru: "60 мин" },
      ];
      el.innerHTML = `
        <h1>${t(L, "titleContact")}</h1>
        <p class="db-lead">${state.instructor.name} · ${fmtDate(state.slot.starts_at, L)}</p>
        <form class="db-form" data-form>
          <label>${t(L, "name")}<input name="student_name" required minlength="2" /></label>
          <label>${t(L, "phone")}<input name="student_phone" required placeholder="+373" /></label>
          <label>${t(L, "email")}<input name="student_email" type="email" /></label>
          <label>${t(L, "lesson")}
            <select name="lesson_type">
              ${types
                .map(
                  (x) =>
                    `<option value="${x.id}">${L === "ru" ? x.title_ru : x.title_ro}${
                      x.price_mdl ? " — " + x.price_mdl + " MDL" : ""
                    }</option>`
                )
                .join("")}
            </select>
          </label>
          <label>${t(L, "notes")}<textarea name="notes" rows="2"></textarea></label>
          <button class="db-btn primary" type="submit">${t(L, "book")}</button>
        </form>`;
      el.querySelector("[data-form]").addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const fd = new FormData(ev.target);
        const btn = ev.target.querySelector("button[type=submit]");
        btn.disabled = true;
        try {
          const body = {
            slot_id: state.slot.id,
            student_name: fd.get("student_name"),
            student_phone: fd.get("student_phone"),
            student_email: fd.get("student_email") || null,
            lesson_type: fd.get("lesson_type"),
            notes: fd.get("notes") || null,
            source: state.source,
            lang: state.lang,
          };
          const res = await api(base, "/v1/bookings", {
            method: "POST",
            body: JSON.stringify(body),
            headers: {
              "Content-Type": "application/json",
              "Idempotency-Key": `w-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            },
          });
          const b = res.booking;
          $('[data-panel="done"]').innerHTML = `
            <div class="db-success">
              <div class="db-check">✓</div>
              <h1>${t(L, "titleDone")}</h1>
              <p>#${b.id}<br>${b.instructor_name}<br>${fmtDate(b.starts_at, L)}</p>
              <button class="db-btn ghost" data-again type="button">${t(L, "again")}</button>
            </div>`;
          setStep("done");
          $("[data-again]").addEventListener("click", () => {
            state.transmission = null;
            state.instructor = null;
            state.slot = null;
            setStep(1);
            renderGear();
          });
        } catch (e) {
          alert(e.message);
        } finally {
          btn.disabled = false;
        }
      });
    }

    $$("[data-set-lang]").forEach((b) =>
      b.addEventListener("click", () => {
        state.lang = b.dataset.setLang;
        applyI18n();
        if (state.step === 1) renderGear();
        else if (state.step === 2) loadInstructors();
        else if (state.step === 3) loadSlots();
        else if (state.step === 4) renderContact();
      })
    );

    $$("[data-goto]").forEach((b) =>
      b.addEventListener("click", () => {
        const s = Number(b.dataset.goto);
        if (s === 1) {
          setStep(1);
          renderGear();
        }
        if (s === 2 && state.transmission !== undefined) {
          setStep(2);
          loadInstructors();
        }
        if (s === 3 && state.instructor) {
          setStep(3);
          loadSlots();
        }
        if (s === 4 && state.slot) {
          setStep(4);
          renderContact();
        }
      })
    );

    applyI18n();
    setStep(1);
    renderGear();
    api(base, "/v1/meta")
      .then((m) => {
        state.meta = m;
      })
      .catch(() => {});

    // ensure CSS link exists in light DOM for non-shadow; shadow injects separately
    if (opts.ensureCssLink && !document.querySelector(`link[href="${cssHref}"]`)) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = cssHref;
      document.head.appendChild(link);
    }

    return { state };
  }

  global.DriveBookWidget = { mount, t, STR };
})(typeof window !== "undefined" ? window : globalThis);
