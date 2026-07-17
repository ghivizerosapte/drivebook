/**
 * DriveBook v2 widget — auto-best primary, instructor calendar secondary.
 * BSM-like 3–4 screens: best slots → (optional instructor calendar) → contacts → done.
 * No deposit UI. Chișinău only. RO/RU/EN.
 */
(function (global) {
  const STR = {
    ro: {
      brand: "DriveBook", city: "Chișinău",
      titleBest: "Cel mai apropiat slot liber",
      titlePick: "Sau alege instructorul",
      titleCal: "Calendar",
      titleContact: "Confirmă rezervarea",
      titleDone: "Ești programat!",
      any: "Oricare", manual: "Manuală", automatic: "Automată",
      zone: "Sector (opțional)", search: "Caută instructor",
      book: "Rezervă", name: "Nume", phone: "Telefon",
      email: "Email (opțional)", again: "Programare nouă",
      empty: "Nimic liber — stai în listă de așteptare",
      waitlist: "Vreau pe listă de așteptare", loading: "Se încarcă…",
      free: "liber", busy: "ocupat", pickSlot: "Alege",
      badge: "programare online", best: "Recomandat", all: "Toți instructorii",
      notes: "Comentariu",
    },
    ru: {
      brand: "DriveBook", city: "Кишинёв",
      titleBest: "Ближайший свободный слот",
      titlePick: "Или выберите инструктора",
      titleCal: "Календарь",
      titleContact: "Подтвердите запись",
      titleDone: "Вы записаны!",
      any: "Любая", manual: "Механика", automatic: "Автомат",
      zone: "Район (необязательно)", search: "Поиск инструктора",
      book: "Записаться", name: "Имя", phone: "Телефон",
      email: "Email (необязательно)", again: "Новая запись",
      empty: "Нет мест — встаньте в лист ожидания",
      waitlist: "В лист ожидания", loading: "Загрузка…",
      free: "свободно", busy: "занято", pickSlot: "Выбрать",
      badge: "онлайн-запись", best: "Рекомендуем", all: "Все инструкторы",
      notes: "Комментарий",
    },
    en: {
      brand: "DriveBook", city: "Chișinău",
      titleBest: "Nearest open slot",
      titlePick: "Or pick an instructor",
      titleCal: "Calendar",
      titleContact: "Confirm booking",
      titleDone: "You're booked!",
      any: "Any", manual: "Manual", automatic: "Automatic",
      zone: "District (optional)", search: "Search instructor",
      book: "Book lesson", name: "Name", phone: "Phone",
      email: "Email (optional)", again: "New booking",
      empty: "Nothing free — join waitlist",
      waitlist: "Join waitlist", loading: "Loading…",
      free: "free", busy: "busy", pickSlot: "Pick",
      badge: "online booking", best: "Recommended", all: "All instructors",
      notes: "Notes",
    },
  };
  const t = (lang, key) => (STR[lang] || STR.ro)[key] || STR.ro[key] || key;
  const fmt = (iso, lang) =>
    new Date(iso).toLocaleString(lang === "ru" ? "ru-RU" : lang === "en" ? "en-GB" : "ro-RO", {
      weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    });

  async function api(base, path, opts) {
    const res = await fetch(base + path, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const d = data.detail;
      const msg = typeof d === "string" ? d : d?.message || `HTTP ${res.status}`;
      const err = new Error(msg);
      err.detail = d;
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function mount(root, options) {
    const opts = options || {};
    const base = opts.apiBase || "";
    const state = {
      lang: opts.lang || "ro",
      source: opts.source || "widget",
      view: "best", // best | instructors | calendar | contact | done
      transmission: "",
      zone: "",
      instructor: null,
      slot: null,
      meta: null,
      alternatives: null,
    };

    root.innerHTML = `
      <div class="db-root"><div class="db-shell">
        <div class="db-top">
          <div class="db-brand"><span>Drive</span>Book · <small data-city></small></div>
          <div class="db-badge" data-badge></div>
        </div>
        <div class="db-lang">
          <button type="button" data-lang="ro">RO</button>
          <button type="button" data-lang="ru">RU</button>
          <button type="button" data-lang="en">EN</button>
        </div>
        <div class="db-body" data-body></div>
        <div class="db-foot">Chișinău · no deposit · multi-channel</div>
      </div></div>`;

    const body = root.querySelector("[data-body]");
    const $ = (s) => root.querySelector(s);

    function applyChrome() {
      $("[data-city]").textContent = t(state.lang, "city");
      $("[data-badge]").textContent = t(state.lang, "badge");
      root.querySelectorAll("[data-lang]").forEach((b) => {
        b.classList.toggle("active", b.dataset.lang === state.lang);
      });
    }

    function track(event_type, payload) {
      api(base, "/v1/events", {
        method: "POST",
        body: JSON.stringify({ event_type, channel: state.source, payload }),
      }).catch(() => {});
    }

    async function renderBest() {
      state.view = "best";
      const L = state.lang;
      body.innerHTML = `
        <h1>${t(L, "titleBest")}</h1>
        <p class="db-lead">${t(L, "city")} · 90 min</p>
        <div class="db-filters">
          <select data-tx>
            <option value="">${t(L, "any")}</option>
            <option value="manual">${t(L, "manual")}</option>
            <option value="automatic">${t(L, "automatic")}</option>
          </select>
          <input data-zone type="text" placeholder="${t(L, "zone")}" value="${state.zone}" />
        </div>
        <div data-list class="db-grid"><div class="db-empty">${t(L, "loading")}</div></div>
        <p style="margin-top:14px"><button type="button" class="db-btn ghost" data-all>${t(L, "all")}</button></p>`;
      body.querySelector("[data-tx]").value = state.transmission;
      body.querySelector("[data-tx]").onchange = (e) => {
        state.transmission = e.target.value;
        loadBest();
      };
      body.querySelector("[data-zone]").onchange = (e) => {
        state.zone = e.target.value.trim();
        loadBest();
      };
      body.querySelector("[data-all]").onclick = () => renderInstructors();
      await loadBest();
    }

    async function loadBest() {
      const L = state.lang;
      const list = body.querySelector("[data-list]");
      if (!list) return;
      list.innerHTML = `<div class="db-empty">${t(L, "loading")}</div>`;
      const p = new URLSearchParams({ limit: "8" });
      if (state.transmission) p.set("transmission", state.transmission);
      if (state.zone) p.set("zone", state.zone);
      if (state.lang) p.set("language", state.lang);
      try {
        const data = await api(base, `/v1/slots/best?${p}`);
        track("slot_viewed", { mode: "best", count: data.items.length });
        if (!data.items.length) {
          list.innerHTML = `<div class="db-empty">${t(L, "empty")}<br>
            <button class="db-btn primary" style="margin-top:10px" data-wl type="button">${t(L, "waitlist")}</button></div>`;
          list.querySelector("[data-wl]").onclick = () => joinWaitlist();
          return;
        }
        list.innerHTML = data.items
          .map(
            (s, i) => `
          <button class="db-card" data-sid="${s.id}" data-iid="${s.instructor_id}">
            ${i === 0 ? `<div class="db-pills"><span class="db-pill">${t(L, "best")}</span></div>` : ""}
            <h3>${fmt(s.starts_at, L)}</h3>
            <p>${s.instructor_name} · ${s.district} · ${s.car}</p>
            <div class="db-pills"><span class="db-pill">${Number(s.rating).toFixed(1)}★</span>
            <span class="db-pill">${s.transmission}</span></div>
          </button>`
          )
          .join("");
        list.querySelectorAll("[data-sid]").forEach((btn) => {
          btn.onclick = () => {
            const item = data.items.find((x) => x.id === Number(btn.dataset.sid));
            state.slot = item;
            state.instructor = {
              id: item.instructor_id,
              name: item.instructor_name,
              district: item.district,
              car: item.car,
            };
            renderContact();
          };
        });
      } catch (e) {
        list.innerHTML = `<div class="db-empty">${e.message}</div>`;
      }
    }

    async function renderInstructors() {
      state.view = "instructors";
      const L = state.lang;
      body.innerHTML = `
        <h1>${t(L, "titlePick")}</h1>
        <div class="db-filters"><input data-q type="search" placeholder="${t(L, "search")}" /></div>
        <div data-list class="db-grid"><div class="db-empty">${t(L, "loading")}</div></div>
        <p><button type="button" class="db-btn ghost" data-back>${t(L, "best")}</button></p>`;
      body.querySelector("[data-back]").onclick = () => renderBest();
      const q = body.querySelector("[data-q]");
      let timer;
      q.oninput = () => {
        clearTimeout(timer);
        timer = setTimeout(loadInst, 250);
      };
      async function loadInst() {
        const list = body.querySelector("[data-list]");
        const p = new URLSearchParams({ limit: "30" });
        if (q.value.trim()) p.set("q", q.value.trim());
        if (state.transmission) p.set("transmission", state.transmission);
        if (state.zone) p.set("zone", state.zone);
        try {
          const data = await api(base, `/v1/instructors?${p}`);
          list.innerHTML = data.items
            .map(
              (i) => `
            <button class="db-card" data-id="${i.id}">
              <h3>${i.name} · ${Number(i.rating).toFixed(1)}★</h3>
              <p>${i.district} · ${i.car} · ${i.transmission}</p>
            </button>`
            )
            .join("") || `<div class="db-empty">${t(L, "empty")}</div>`;
          list.querySelectorAll("[data-id]").forEach((btn) => {
            btn.onclick = () => {
              state.instructor = data.items.find((x) => x.id === Number(btn.dataset.id));
              renderCalendar();
            };
          });
        } catch (e) {
          list.innerHTML = `<div class="db-empty">${e.message}</div>`;
        }
      }
      await loadInst();
    }

    async function renderCalendar() {
      state.view = "calendar";
      const L = state.lang;
      body.innerHTML = `
        <h1>${t(L, "titleCal")}</h1>
        <p class="db-lead">${state.instructor.name} · ${state.instructor.district}</p>
        <div data-cal class="db-grid"><div class="db-empty">${t(L, "loading")}</div></div>
        <p><button type="button" class="db-btn ghost" data-back>${t(L, "all")}</button></p>`;
      body.querySelector("[data-back]").onclick = () => renderInstructors();
      try {
        const cal = await api(base, `/v1/instructors/${state.instructor.id}/calendar`);
        track("slot_viewed", { mode: "calendar", instructor_id: state.instructor.id });
        const days = Object.keys(cal.days || {}).sort();
        if (!days.length) {
          body.querySelector("[data-cal]").innerHTML = `<div class="db-empty">${t(L, "empty")}<br>
            <button class="db-btn primary" data-wl type="button">${t(L, "waitlist")}</button></div>`;
          body.querySelector("[data-wl]").onclick = () => joinWaitlist(state.instructor.id);
          return;
        }
        body.querySelector("[data-cal]").innerHTML = days
          .map((day) => {
            const slots = cal.days[day];
            return `<div class="db-card" style="cursor:default">
              <h3>${day}</h3>
              <div class="db-slots" style="margin-top:8px">
                ${slots
                  .map(
                    (s) =>
                      s.free
                        ? `<button class="db-slot" data-id="${s.id}"><strong>${fmt(s.starts_at, L)}</strong><span>${t(L, "free")}</span></button>`
                        : `<button class="db-slot" disabled style="opacity:.45"><strong>${fmt(s.starts_at, L)}</strong><span>${t(L, "busy")}</span></button>`
                  )
                  .join("")}
              </div></div>`;
          })
          .join("");
        body.querySelectorAll("[data-id]").forEach((btn) => {
          btn.onclick = async () => {
            const slots = await api(base, `/v1/slots?instructor_id=${state.instructor.id}&limit=100`);
            state.slot = slots.items.find((x) => x.id === Number(btn.dataset.id));
            if (state.slot) renderContact();
          };
        });
      } catch (e) {
        body.querySelector("[data-cal]").innerHTML = `<div class="db-empty">${e.message}</div>`;
      }
    }

    function renderContact() {
      state.view = "contact";
      const L = state.lang;
      body.innerHTML = `
        <h1>${t(L, "titleContact")}</h1>
        <p class="db-lead">${state.instructor.name}<br>${fmt(state.slot.starts_at, L)}</p>
        <form class="db-form" data-form>
          <label>${t(L, "name")}<input name="student_name" required minlength="2" /></label>
          <label>${t(L, "phone")}<input name="student_phone" required placeholder="+373" /></label>
          <label>${t(L, "email")}<input name="student_email" type="email" /></label>
          <label>${t(L, "notes")}<textarea name="notes" rows="2"></textarea></label>
          <button class="db-btn primary" type="submit">${t(L, "book")}</button>
        </form>
        <div data-alts></div>`;
      body.querySelector("[data-form]").onsubmit = async (ev) => {
        ev.preventDefault();
        const fd = new FormData(ev.target);
        const btn = ev.target.querySelector("button");
        btn.disabled = true;
        try {
          const res = await api(base, "/v1/bookings", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Idempotency-Key": `w-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            },
            body: JSON.stringify({
              slot_id: state.slot.id,
              student_name: fd.get("student_name"),
              student_phone: fd.get("student_phone"),
              student_email: fd.get("student_email") || null,
              notes: fd.get("notes") || null,
              source: state.source,
              lang: state.lang,
            }),
          });
          renderDone(res.booking);
        } catch (e) {
          if (e.status === 409 && e.detail?.alternatives?.length) {
            const alts = e.detail.alternatives;
            body.querySelector("[data-alts]").innerHTML = `
              <p class="db-lead">${e.message}</p>
              <div class="db-grid">${alts
                .map(
                  (a) =>
                    `<button class="db-card" data-alt="${a.slot_id}">
                      <h3>${fmt(a.starts_at, L)}</h3>
                      <p>${a.instructor_name} · ${a.district}</p>
                    </button>`
                )
                .join("")}</div>`;
            body.querySelectorAll("[data-alt]").forEach((b) => {
              b.onclick = () => {
                state.slot = { id: Number(b.dataset.alt), starts_at: alts.find((x) => x.slot_id === Number(b.dataset.alt)).starts_at };
                state.instructor = {
                  name: alts.find((x) => x.slot_id === Number(b.dataset.alt)).instructor_name,
                  district: alts.find((x) => x.slot_id === Number(b.dataset.alt)).district,
                };
                renderContact();
              };
            });
          } else alert(e.message);
        } finally {
          btn.disabled = false;
        }
      };
    }

    function renderDone(b) {
      state.view = "done";
      const L = state.lang;
      body.innerHTML = `
        <div class="db-success">
          <div class="db-check">✓</div>
          <h1>${t(L, "titleDone")}</h1>
          <p>#${b.id}<br>${b.instructor_name}<br>${fmt(b.starts_at, L)}</p>
          <button class="db-btn ghost" data-again type="button">${t(L, "again")}</button>
        </div>`;
      body.querySelector("[data-again]").onclick = () => {
        state.slot = null;
        state.instructor = null;
        renderBest();
      };
    }

    async function joinWaitlist(instructorId) {
      const name = prompt(t(state.lang, "name"));
      const phone = prompt(t(state.lang, "phone"));
      if (!name || !phone) return;
      try {
        await api(base, "/v1/waitlist", {
          method: "POST",
          body: JSON.stringify({
            student_name: name,
            student_phone: phone,
            instructor_id: instructorId || null,
            zone: state.zone || null,
            lang: state.lang,
            source: state.source,
          }),
        });
        alert("OK · waitlist");
      } catch (e) {
        alert(e.message);
      }
    }

    root.querySelectorAll("[data-lang]").forEach((b) => {
      b.onclick = () => {
        state.lang = b.dataset.lang;
        applyChrome();
        if (state.view === "best") renderBest();
        else if (state.view === "instructors") renderInstructors();
        else if (state.view === "calendar") renderCalendar();
        else if (state.view === "contact") renderContact();
      };
    });

    applyChrome();
    api(base, "/v1/meta").then((m) => { state.meta = m; }).catch(() => {});
    renderBest();
    return { state };
  }

  global.DriveBookWidget = { mount };
})(typeof window !== "undefined" ? window : globalThis);
