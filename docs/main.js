/* Events Radar front-end. All filtering happens in the browser from events.json. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];

  const FACETS = [
    { key: "type",        label: "Event type" },
    { key: "tracks",      label: "Track" },
    { key: "format",      label: "Format" },
    { key: "hubs",        label: "Location" },
    { key: "eligibility", label: "Who it's for" },
    { key: "host",        label: "Host", searchable: true },
    { key: "source",      label: "Source" },
  ];
  const PAGE = 50;
  const TAB_TYPES = {
    hackathons: ["Hackathon"], competitions: ["Competition"],
    programs: ["Insight program", "Fellowship", "Winternship", "Firm event"],
    conferences: ["Conference", "Career fair"],
  };

  const state = {
    events: [], tab: "upcoming", sort: "date", q: "", limit: PAGE, hideApprox: false,
    filters: Object.fromEntries(FACETS.map(f => [f.key, new Set()])),
    open: new Set(), collapsedFacets: new Set(["eligibility", "host", "source"]), facetShowAll: new Set(),
  };

  // ------------------------------------------------------------ URL state
  function readUrl() {
    const p = new URLSearchParams(location.search);
    for (const f of FACETS) if (p.get(f.key)) state.filters[f.key] = new Set(p.get(f.key).split("|"));
    if (p.get("tab")) state.tab = p.get("tab");
    if (p.get("sort")) state.sort = p.get("sort");
    if (p.get("q")) state.q = p.get("q");
    if (p.get("confirmed") === "1") state.hideApprox = true;
  }
  function writeUrl() {
    const p = new URLSearchParams();
    for (const f of FACETS) if (state.filters[f.key].size) p.set(f.key, [...state.filters[f.key]].join("|"));
    if (state.tab !== "upcoming") p.set("tab", state.tab);
    if (state.sort !== "date") p.set("sort", state.sort);
    if (state.q) p.set("q", state.q);
    if (state.hideApprox) p.set("confirmed", "1");
    history.replaceState(null, "", p.toString() ? "?" + p : location.pathname);
  }

  // ------------------------------------------------------------ helpers
  const dayMs = 86400000;
  const today = () => new Date(new Date().toDateString());
  const toDate = iso => iso ? new Date(iso.slice(0, 10) + "T00:00:00") : null;
  const daysUntil = iso => Math.round((toDate(iso) - today()) / dayMs);
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fmtD = iso => { const d = toDate(iso); return d ? `${MON[d.getMonth()]} ${d.getDate()}` : ""; };
  const monthKey = iso => { const d = toDate(iso); return d ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}` : "9999-99"; };
  const monthLabel = k => k === "9999-99" ? "Rolling / date to be announced" : `${["January","February","March","April","May","June","July","August","September","October","November","December"][+k.slice(5) - 1]} ${k.slice(0, 4)}`;
  const ago = iso => { const d = Math.floor((today() - toDate(iso)) / dayMs); return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d}d ago`; };
  const isNew = e => (Date.now() - new Date(e.first_seen)) < 3 * dayMs;
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const vals = (e, key) => Array.isArray(e[key]) ? e[key] : [e[key] ?? "Not specified"];
  const sortDate = e => e.deadline && (!e.start || e.deadline < e.start) && daysUntil(e.deadline) >= 0 ? e.deadline : (e.start || "9999-12-31");

  // ------------------------------------------------------------ filtering
  function tabPass(e) {
    const s = e.user_status;
    if (s === "hidden" && state.tab !== "hidden") return false;
    if (state.tab === "saved") return s === "saved";
    if (state.tab === "registered") return s === "registered";
    if (!e.active) return false;
    if (state.tab === "deadlines") return !!e.deadline && daysUntil(e.deadline) >= 0;
    if (TAB_TYPES[state.tab]) return TAB_TYPES[state.tab].includes(e.type);
    return true; // upcoming
  }
  function facetPass(e, skipKey) {
    for (const f of FACETS) {
      if (f.key === skipKey) continue;
      const sel = state.filters[f.key];
      if (sel.size && !vals(e, f.key).some(v => sel.has(v))) return false;
    }
    return true;
  }
  const queryPass = e => !state.q || (e.title + " " + e.host + " " + e.location + " " + e.description).toLowerCase().includes(state.q.toLowerCase());
  const approxPass = e => !state.hideApprox || !e.approx;
  const base = () => state.events.filter(e => tabPass(e) && queryPass(e) && approxPass(e));

  function sortEvents(list) {
    if (state.sort === "added") return list.sort((a, b) => b.first_seen.localeCompare(a.first_seen));
    if (state.sort === "deadline") return list.sort((a, b) => (a.deadline || "9999").localeCompare(b.deadline || "9999") || sortDate(a).localeCompare(sortDate(b)));
    const k = e => monthKey(sortDate(e)) + (e.approx ? "1" : "0") + sortDate(e);   // confirmed dates first within a month
    return list.sort((a, b) => k(a).localeCompare(k(b)) || a.title.localeCompare(b.title));
  }

  // ------------------------------------------------------------ facets
  function renderFacets() {
    const root = $("#facets");
    root.innerHTML = "";
    let active = 0;
    for (const f of FACETS) {
      const pool = base().filter(e => facetPass(e, f.key));
      const counts = new Map();
      for (const e of pool) for (const v of vals(e, f.key)) counts.set(v, (counts.get(v) || 0) + 1);
      for (const v of state.filters[f.key]) if (!counts.has(v)) counts.set(v, 0);
      const opts = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      const sel = state.filters[f.key];
      active += sel.size ? 1 : 0;
      const collapsed = state.collapsedFacets.has(f.key), showAll = state.facetShowAll.has(f.key);
      const shown = showAll ? opts : opts.slice(0, 8);
      const el = document.createElement("div");
      el.className = "facet";
      el.innerHTML = `
        <button class="facet-head" data-toggle="${f.key}">
          <span>${f.label}${sel.size ? ` <span class="sel">· ${sel.size} selected</span>` : ""}</span><span class="chev">${collapsed ? "▶" : "▼"}</span>
        </button>
        <div class="facet-body ${collapsed ? "collapsed" : ""}">
          ${f.searchable ? `<input class="facet-search" placeholder="Find ${f.label.toLowerCase()}…">` : ""}
          ${shown.map(([v, n]) => `<label class="opt"><input type="checkbox" data-key="${f.key}" value="${esc(v)}" ${sel.has(v) ? "checked" : ""}> <span>${esc(v)}</span><span class="n">${n}</span></label>`).join("")}
          ${opts.length > 8 ? `<button class="facet-more" data-more="${f.key}">${showAll ? "Show fewer" : `Show all ${opts.length}`}</button>` : ""}
        </div>`;
      root.appendChild(el);
    }
    $("#active-filter-count").textContent = active + (state.q ? 1 : 0) + (state.hideApprox ? 1 : 0);
  }

  // ------------------------------------------------------------ list
  function renderList() {
    const list = sortEvents(base().filter(e => facetPass(e)));
    const total = list.length;
    $("#match-count").textContent = `${total} event${total === 1 ? "" : "s"}`;
    $("#page-title").textContent = { upcoming: "Upcoming events", deadlines: "Upcoming deadlines", hackathons: "Hackathons", competitions: "Competitions & challenges", programs: "Firm programs & insight days", conferences: "Conferences & career fairs", saved: "Saved events", registered: "Registered", hidden: "Hidden" }[state.tab] || "Events";
    const slice = list.slice(0, state.limit);
    const root = $("#list");
    root.innerHTML = "";
    if (!total) root.innerHTML = `<div class="empty">Nothing matches. Try clearing a filter.</div>`;
    let curMonth = null, wrap = null;
    slice.forEach((e, i) => {
      const k = state.sort === "date" ? monthKey(sortDate(e)) : null;
      if (k !== null && k !== curMonth) {
        curMonth = k;
        const h = document.createElement("div"); h.className = "month-head"; h.textContent = monthLabel(k); root.appendChild(h);
        wrap = document.createElement("div"); wrap.className = "company"; root.appendChild(wrap);
      } else if (!wrap) { wrap = document.createElement("div"); wrap.className = "company"; root.appendChild(wrap); }
      wrap.insertAdjacentHTML("beforeend", rowHtml(e, i + 1));
    });
    $("#showing").textContent = total ? `${Math.min(state.limit, total)} of ${total} showing` : "";
    $("#load-more").classList.toggle("hidden", state.limit >= total);
    $("#load-more").textContent = `Load more (${Math.max(0, total - state.limit)} remaining)`;
  }

  function dateBox(e) {
    if (e.approx || !e.start) {
      const d = toDate(e.start);
      return `<div class="datebox approx"><div class="mon">${d ? MON[d.getMonth()] : "TBA"}</div><div class="day">${d ? "typically" : "rolling"}</div></div>`;
    }
    const s = toDate(e.start), en = toDate(e.end || e.start);
    const range = en && en > s ? `– ${MON[en.getMonth()]} ${en.getDate()}` : "";
    return `<div class="datebox"><div class="mon">${MON[s.getMonth()]}</div><div class="day">${s.getDate()}</div><div class="range">${range || s.getFullYear()}</div></div>`;
  }

  function rowHtml(e, rank) {
    const st = e.user_status;
    let dl = "";
    if (e.deadline) {
      const n = daysUntil(e.deadline);
      dl = n < 0 ? `<span class="tag approxtag">Deadline passed ${fmtD(e.deadline)}</span>` : `<span class="tag dl ${n <= 7 ? "soon" : ""}">Apply by ${fmtD(e.deadline)} · ${n === 0 ? "today" : n + "d left"}</span>`;
    }
    const meta = [
      e.format && e.format !== "Varies" ? `🏢 ${esc(e.format)}` : "",
      `📍 ${esc(e.location || e.hubs.join(", ") || "Not specified")}`,
      e.eligibility ? `🎓 ${esc(e.eligibility)}` : "",
      `Added ${ago(e.first_seen)}`,
    ].filter(Boolean).map(x => `<span>${x}</span>`).join("");
    return `
      <div class="role ${st === "hidden" || !e.active ? "dim" : ""}" data-id="${e.id}">
        ${dateBox(e)}
        <div>
          <div class="role-title">
            <a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>
            <span class="tag type">${esc(e.type)}</span>
            ${e.tracks.map(t => `<span class="tag track">${esc(t)}</span>`).join("")}
            ${dl}
            ${isNew(e) && e.active ? `<span class="tag new">New</span>` : ""}
            ${e.approx ? `<span class="tag approxtag">typical timing</span>` : ""}
            ${!e.active ? `<span class="tag approxtag">No longer listed</span>` : ""}
            ${st ? `<span class="tag status">${st}</span>` : ""}
          </div>
          <div class="when"><span class="host">${esc(e.host)}</span>${e.when ? ` · ${esc(e.when)}` : ""}</div>
          <div class="role-meta">${meta}</div>
          ${state.open.has(e.id) ? `<div class="details" style="margin-top:10px"><div class="src">Source: ${esc(e.source)} · first seen ${e.first_seen.slice(0, 10)} · last checked ${e.last_seen.slice(0, 10)}${e.page_status === "unreachable" ? " · page was unreachable on the last check" : ""}</div>${esc(e.description || "No description captured — open the event page.")}</div>` : ""}
        </div>
        <div class="actions">
          <button class="btn" data-act="details" data-id="${e.id}">${state.open.has(e.id) ? "Hide details" : "Details"}</button>
          <button class="btn ${st === "saved" ? "on" : ""}" data-act="saved" data-id="${e.id}">${st === "saved" ? "Saved ✓" : "Save"}</button>
          <button class="btn ${st === "registered" ? "on" : ""}" data-act="registered" data-id="${e.id}">${st === "registered" ? "Registered ✓" : "Mark registered"}</button>
          <button class="btn ${st === "hidden" ? "on" : ""}" data-act="hidden" data-id="${e.id}">${st === "hidden" ? "Unhide" : "Hide"}</button>
          ${e.start && !e.approx ? `<a class="btn" href="${icsHref(e)}" download="${esc(e.title.replace(/[^a-z0-9]+/gi, "-"))}.ics" title="Add to calendar">📅</a>` : ""}
          <a class="btn apply" href="${esc(e.url)}" target="_blank" rel="noopener">Register →</a>
        </div>
      </div>`;
  }

  function icsHref(e) {
    const d = iso => iso.slice(0, 10).replace(/-/g, "");
    const end = toDate(e.end || e.start); end.setDate(end.getDate() + 1);
    const endStr = `${end.getFullYear()}${String(end.getMonth() + 1).padStart(2, "0")}${String(end.getDate()).padStart(2, "0")}`;
    const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Events Radar//EN", "BEGIN:VEVENT", `UID:${e.id}@eventsradar`,
      `DTSTART;VALUE=DATE:${d(e.start)}`, `DTEND;VALUE=DATE:${endStr}`, `SUMMARY:${e.title.replace(/,/g, "\\,")}`,
      `DESCRIPTION:${(e.host + " — " + e.url).replace(/,/g, "\\,")}`, `LOCATION:${(e.location || "").replace(/,/g, "\\,")}`, `URL:${e.url}`, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
    return "data:text/calendar;charset=utf-8," + encodeURIComponent(ics);
  }

  function render() { renderFacets(); renderList(); renderCounts(); writeUrl(); }
  function renderCounts() { for (const s of ["saved", "registered"]) $(`#cnt-${s}`).textContent = state.events.filter(e => e.user_status === s).length; }

  // ------------------------------------------------------------ events
  document.addEventListener("click", e => {
    const t = e.target.closest("button, a");
    if (!t) return;
    if (t.dataset.tab) { state.tab = t.dataset.tab; state.limit = PAGE; $$("#tabs button").forEach(b => b.classList.toggle("active", b === t)); render(); }
    else if (t.dataset.sort) { state.sort = t.dataset.sort; $$(".sort button").forEach(b => b.classList.toggle("active", b === t)); renderList(); writeUrl(); }
    else if (t.dataset.toggle) { const k = t.dataset.toggle; state.collapsedFacets.has(k) ? state.collapsedFacets.delete(k) : state.collapsedFacets.add(k); renderFacets(); }
    else if (t.dataset.more) { const k = t.dataset.more; state.facetShowAll.has(k) ? state.facetShowAll.delete(k) : state.facetShowAll.add(k); renderFacets(); }
    else if (t.id === "load-more") { state.limit += PAGE; renderList(); }
    else if (t.id === "reset-filters") { for (const f of FACETS) state.filters[f.key].clear(); state.q = ""; $("#q").value = ""; state.hideApprox = false; $("#hide-approx").checked = false; state.limit = PAGE; render(); }
    else if (t.id === "share-btn") { e.preventDefault(); navigator.clipboard?.writeText(location.href); t.textContent = "Link copied ✓"; setTimeout(() => t.textContent = "Share view", 1500); }
    else if (t.dataset.act === "details") { const id = t.dataset.id; state.open.has(id) ? state.open.delete(id) : state.open.add(id); renderList(); }
    else if (t.dataset.act) {
      const ev = state.events.find(x => x.id === t.dataset.id);
      const next = ev.user_status === t.dataset.act ? null : t.dataset.act;
      ev.user_status = next; saveStatus(ev.id, next); render();
    }
  });
  document.addEventListener("change", e => {
    const t = e.target;
    if (t.matches(".facet-body input[type=checkbox]")) { const set = state.filters[t.dataset.key]; t.checked ? set.add(t.value) : set.delete(t.value); state.limit = PAGE; render(); }
    else if (t.id === "hide-approx") { state.hideApprox = t.checked; render(); }
  });
  document.addEventListener("input", e => {
    const t = e.target;
    if (t.id === "q") { state.q = t.value.trim(); state.limit = PAGE; render(); }
    else if (t.matches(".facet-search")) { const q = t.value.toLowerCase(); $$(".opt", t.parentElement).forEach(o => o.classList.toggle("hidden", !o.textContent.toLowerCase().includes(q))); }
  });

  // ------------------------------------------------------------ data
  const LS_KEY = "eventsradar.status";
  const loadStatuses = () => { try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch { return {}; } };
  function saveStatus(id, status) { const all = loadStatuses(); if (status) all[id] = status; else delete all[id]; try { localStorage.setItem(LS_KEY, JSON.stringify(all)); } catch {} }
  async function load() {
    const r = await fetch("events.json", { cache: "no-cache" }).then(r => r.json());
    const st = loadStatuses();
    state.events = r.events.map(e => ({ ...e, user_status: st[e.id] || null }));
    const h = Math.round((Date.now() - new Date(r.generated_at)) / 3600000);
    $("#last-run").textContent = `Updated ${h < 1 ? "just now" : h < 24 ? h + "h ago" : ago(r.generated_at)} · ${r.last_run?.total_active ?? state.events.length} events`;
    render();
  }

  readUrl();
  $("#q").value = state.q; $("#hide-approx").checked = state.hideApprox;
  $$("#tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === state.tab));
  $$(".sort button").forEach(b => b.classList.toggle("active", b.dataset.sort === state.sort));
  load();
})();
