"""Shared HTML shell: <head>, header, CSS, and common JavaScript."""

from __future__ import annotations


def head_html() -> str:
    """Return everything inside <head> including meta, fonts, Tailwind config, and all CSS."""
    return """\
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>TRACR</title>
    <link rel="icon" type="image/png" href="/web/tracr.png" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet" />
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      tailwind.config = {
        darkMode: 'class',
        theme: {
          extend: {
            fontFamily: {
              sans: ['Geist', 'system-ui', '-apple-system', 'sans-serif'],
              mono: ['Geist Mono', 'ui-monospace', 'monospace'],
            },
            colors: {
              g: {
                bg:      'var(--c-bg)',
                subtle:  'var(--c-subtle)',
                surface: 'var(--c-surface)',
                panel:   'var(--c-panel)',
                raised:  'var(--c-raised)',
                border:  'var(--c-border)',
                hover:   'var(--c-hover)',
                muted:   'var(--c-muted)',
                dim:     'var(--c-dim)',
                text:    'var(--c-text)',
                bright:  'var(--c-bright)',
              }
            },
          }
        }
      }
    </script>
    <style>
      /* ---- Theme tokens ---- */
      :root, html.light {
        --c-bg: #f8f9fb; --c-subtle: #f0f1f4; --c-surface: #ffffff;
        --c-panel: #f5f6f8; --c-raised: #edeef1; --c-border: #d5d8de;
        --c-hover: #c8ccd4; --c-muted: #7b8494; --c-dim: #5a6376;
        --c-text: #1e2330; --c-bright: #0d1017;
        --c-dd-ring: rgba(0,0,0,0.05); --c-dd-shadow: 0 4px 16px rgba(0,0,0,0.08);
        --c-scrollthumb: #c8ccd4; --c-scrollthumb-hover: #a0a6b4;
      }
      html.dark {
        --c-bg: #0a0c10; --c-subtle: #12151b; --c-surface: #171b22;
        --c-panel: #1c2129; --c-raised: #232a33; --c-border: #2a3241;
        --c-hover: #343f50; --c-muted: #545f72; --c-dim: #7c889c;
        --c-text: #c8ced8; --c-bright: #e8ecf2;
        --c-dd-ring: rgba(255,255,255,0.05); --c-dd-shadow: 0 4px 16px rgba(0,0,0,0.5);
        --c-scrollthumb: #2a3241; --c-scrollthumb-hover: #343f50;
      }
      :root { --pdf-zoom: 1; --md-zoom: 1; }
      html { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }

      /* Scrollbar */
      ::-webkit-scrollbar { width: 5px; height: 5px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: var(--c-scrollthumb); border-radius: 3px; }
      ::-webkit-scrollbar-thumb:hover { background: var(--c-scrollthumb-hover); }

      /* Number input stepper hide */
      input[type="number"]::-webkit-inner-spin-button,
      input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
      input[type="number"] { -moz-appearance: textfield; }

      /* Section transitions */
      .section { display: none; }
      .section.active { display: block; animation: fadeUp 180ms ease; }
      @keyframes fadeUp { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: translateY(0); } }

      /* Viewer grid */
      .viewer-grid { height: 76vh; }

      /* ELO arena grid */
      .elo-arena-grid { height: 68vh; }
      .elo-scroll-panel { min-height: 0; }

      /* PDF panel: image starts fit-to-height, zoom multiplies from there */
      .pdf-scroll-area {
        display: flex; align-items: center; justify-content: center;
        flex: 1; padding: 12px; background: var(--c-subtle);
        overflow: hidden; /* default: no scroll at fit */
        position: relative;
      }
      .pdf-scroll-area.scrollable { overflow: auto; }
      #viewer-image {
        /* baseline: fit whole page in the panel height */
        height: calc(var(--pdf-zoom) * 100%);
        width: auto; max-width: none; max-height: none;
        object-fit: contain;
        transition: height 150ms ease;
      }

      /* MD zoom: CSS zoom on wrapper */
      .md-zoom-wrapper {
        zoom: var(--md-zoom);
        -moz-transform: scale(var(--md-zoom));
        -moz-transform-origin: top left;
        transition: zoom 150ms ease;
      }

      /* Zoom slider styling */
      input[type="range"].zoom-slider {
        -webkit-appearance: none; appearance: none;
        height: 4px; border-radius: 2px; outline: none; cursor: pointer;
        background: linear-gradient(to right, #3b82f6 0%, #3b82f6 var(--fill, 50%), var(--c-border) var(--fill, 50%), var(--c-border) 100%);
      }
      input[type="range"].zoom-slider::-webkit-slider-thumb {
        -webkit-appearance: none; width: 14px; height: 14px;
        border-radius: 50%; background: #3b82f6; border: 2px solid var(--c-surface);
        box-shadow: 0 1px 3px rgba(0,0,0,0.3); cursor: pointer;
      }
      input[type="range"].zoom-slider::-moz-range-thumb {
        width: 14px; height: 14px; border-radius: 50%; background: #3b82f6;
        border: 2px solid var(--c-surface); box-shadow: 0 1px 3px rgba(0,0,0,0.3); cursor: pointer;
      }

      /* Rendered markdown */
      .md-rendered { line-height: 1.7; font-size: 14px; }
      .md-rendered h1,.md-rendered h2,.md-rendered h3,.md-rendered h4,.md-rendered h5,.md-rendered h6 {
        margin-top: 1.1em; margin-bottom: 0.4em; font-weight: 600; line-height: 1.3; color: var(--c-bright);
      }
      .md-rendered h1 { font-size: 1.5em; } .md-rendered h2 { font-size: 1.25em; } .md-rendered h3 { font-size: 1.1em; }
      .md-rendered p { margin: 0.5em 0; }
      .md-rendered ul,.md-rendered ol { padding-left: 1.5em; margin: 0.5em 0; }
      .md-rendered li { margin: 0.2em 0; }
      .md-rendered code { font-family: 'Geist Mono', monospace; font-size: 0.87em; background: var(--c-raised); padding: 1px 5px; border-radius: 4px; color: #60a5fa; }
      .md-rendered pre { background: var(--c-panel); border: 1px solid var(--c-border); border-radius: 8px; padding: 12px 14px; overflow-x: auto; margin: 0.7em 0; }
      .md-rendered pre code { background: none; padding: 0; color: var(--c-text); }
      .md-rendered table { width: 100%; border-collapse: collapse; margin: 0.7em 0; font-size: 13px; }
      .md-rendered th,.md-rendered td { border: 1px solid var(--c-border); padding: 5px 10px; text-align: left; }
      .md-rendered th { background: var(--c-panel); font-weight: 600; color: var(--c-dim); }
      .md-rendered blockquote { border-left: 3px solid #3b82f6; padding-left: 12px; margin: 0.7em 0; color: var(--c-dim); }
      .md-rendered img { max-width: 100%; border-radius: 8px; }
      .md-rendered a { color: #60a5fa; text-decoration: none; } .md-rendered a:hover { text-decoration: underline; }

      /* Toast */
      @keyframes toastIn { from { opacity: 0; transform: translateY(6px) scale(0.97); } to { opacity: 1; transform: translateY(0) scale(1); } }
      @keyframes toastOut { from { opacity: 1; transform: translateY(0) scale(1); } to { opacity: 0; transform: translateY(6px) scale(0.97); } }
      .toast-enter { animation: toastIn 200ms ease; }
      .toast-leave { animation: toastOut 180ms ease forwards; }

      /* Dropdown */
      @keyframes ddIn { from { opacity: 0; transform: scale(0.95) translateY(-4px); } to { opacity: 1; transform: scale(1) translateY(0); } }
      .dd-panel { animation: ddIn 100ms ease; box-shadow: var(--c-dd-shadow); }

      /* Spinner */
      @keyframes spin { to { transform: rotate(360deg); } }
      .spin { animation: spin 550ms linear infinite; }
    </style>"""


def header_html() -> str:
    """Return the header bar with logo, theme toggle, and tab switcher."""
    return """\
      <!-- Header -->
      <header class="flex items-center justify-between pb-3.5 mb-3.5 border-b border-g-border">
        <div class="flex items-center gap-3">
          <div class="w-14 h-14 rounded-lg overflow-hidden flex items-center justify-center select-none">
            <img src="/web/tracr.png" alt="TRACR" class="w-full h-full object-cover" />
          </div>
          <div>
            <h1 class="text-[15px] font-bold tracking-wide text-g-bright">TRACR</h1>
            <p class="text-[11px] text-g-muted leading-tight">OCR output reviewer &amp; quality comparison</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <!-- Theme toggle -->
          <div class="flex bg-g-surface border border-g-border rounded-lg p-0.5 gap-0.5">
            <button class="theme-btn px-2 py-1.5 rounded-md text-[12px] cursor-pointer transition-all duration-150 border-0 bg-transparent text-g-dim" data-theme="light" title="Light">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/></svg>
            </button>
            <button class="theme-btn px-2 py-1.5 rounded-md text-[12px] cursor-pointer transition-all duration-150 border-0 bg-transparent text-g-dim" data-theme="dark" title="Dark">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z"/></svg>
            </button>
            <button class="theme-btn px-2 py-1.5 rounded-md text-[12px] cursor-pointer transition-all duration-150 border-0 bg-transparent text-g-dim" data-theme="system" title="System">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
            </button>
          </div>
          <!-- Tab switcher -->
          <div class="flex bg-g-surface border border-g-border rounded-lg p-0.5 gap-0.5">
            <button class="tab active px-4 py-1.5 rounded-md text-[13px] font-medium cursor-pointer transition-all duration-150 border-0 bg-transparent text-g-dim" data-tab="viewer">Viewer</button>
            <button class="tab px-4 py-1.5 rounded-md text-[13px] font-medium cursor-pointer transition-all duration-150 border-0 bg-transparent text-g-dim" data-tab="elo">ELO Arena</button>
          </div>
        </div>
      </header>"""


def shared_js() -> str:
    """Return shared JS: state, theme, Dropdown class, zoom, toast, tabs, fetchJSON."""
    return """\
      const PDF_ZOOM_MIN = 100, PDF_ZOOM_MAX = 400, PDF_ZOOM_STEP = 10;
      const MD_ZOOM_MIN = 50, MD_ZOOM_MAX = 200, MD_ZOOM_STEP = 5;
      const state = {
        viewer: { jobs: [], outputs: [], rendered: true, jobId: null, outputId: null, pageNumber: null },
        elo: { jobs: [], pair: null, rendered: false, jobId: null, _cols: 3, arenaMode: true, browsePages: [], browseIdx: -1, browseModels: null },
        pdfZoom: 100,
        mdZoom: 100
      };
      let viewerRefreshTimer = null;

      function byId(id) { return document.getElementById(id); }

      /* ============ Theme system ============ */
      function getSystemTheme() { return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; }

      function applyTheme(mode) {
        const resolved = mode === 'system' ? getSystemTheme() : mode;
        document.documentElement.classList.toggle('dark', resolved === 'dark');
        document.documentElement.classList.toggle('light', resolved === 'light');
        localStorage.setItem('tracr-theme', mode);
        document.querySelectorAll('.theme-btn').forEach(btn => {
          const active = btn.dataset.theme === mode;
          btn.classList.toggle('bg-blue-500/10', active);
          btn.classList.toggle('text-blue-400', active);
          if (!active) { btn.classList.remove('bg-blue-500/10', 'text-blue-400'); }
        });
      }
      (function() {
        const saved = localStorage.getItem('tracr-theme') || 'dark';
        applyTheme(saved);
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
          if (localStorage.getItem('tracr-theme') === 'system') applyTheme('system');
        });
      })();

      /* ============ Custom Dropdown System ============ */
      class Dropdown {
        constructor(el, onChange) {
          this.root = el;
          this.trigger = el.querySelector('.dd-trigger');
          this.label = el.querySelector('.dd-label');
          this.menu = el.querySelector('.dd-menu');
          this.list = this.menu.querySelector('.max-h-60');
          this.onChange = onChange;
          this.value = null;
          this._open = false;
          this.trigger.addEventListener('click', (e) => { e.stopPropagation(); this.toggle(); });
        }
        toggle() { this._open ? this.close() : this.open(); }
        open() {
          document.querySelectorAll('.dd-menu:not(.hidden)').forEach(m => {
            if (m !== this.menu) m.classList.add('hidden');
          });
          document.querySelectorAll('.dd').forEach(d => { if (d !== this.root) d._dd && (d._dd._open = false); });
          this.menu.classList.remove('hidden');
          this._open = true;
          const active = this.list.querySelector('[data-active="true"]');
          if (active) active.scrollIntoView({ block: 'nearest' });
        }
        close() { this.menu.classList.add('hidden'); this._open = false; }
        setItems(items, valueKey, labelKey) {
          this.list.innerHTML = '';
          if (!items.length) {
            this.list.innerHTML = '<div class="px-3 py-2.5 text-[13px] text-g-muted">No options</div>';
            this.value = null;
            this.label.textContent = 'No options';
            return;
          }
          for (const item of items) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.dataset.value = String(item[valueKey]);
            btn.className = 'dd-item flex items-center w-full text-left px-3 py-1.5 text-[13px] text-g-text hover:bg-g-raised cursor-pointer transition-colors';
            btn.innerHTML = `<span class="truncate">${this._esc(String(item[labelKey]))}</span><svg class="dd-check w-4 h-4 ml-auto text-blue-500 shrink-0 hidden" fill="none" viewBox="0 0 20 20"><path stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M5 10l3 3 7-7"/></svg>`;
            btn.addEventListener('click', (e) => { e.stopPropagation(); this.select(btn.dataset.value); this.close(); });
            this.list.appendChild(btn);
          }
        }
        select(val) {
          this.value = val;
          this.list.querySelectorAll('.dd-item').forEach(btn => {
            const isActive = btn.dataset.value === val;
            btn.dataset.active = String(isActive);
            btn.classList.toggle('bg-g-raised/50', isActive);
            btn.querySelector('.dd-check').classList.toggle('hidden', !isActive);
          });
          const active = this.list.querySelector('[data-active="true"]');
          if (active) this.label.textContent = active.querySelector('span').textContent;
          if (this.onChange) this.onChange(val);
        }
        selectSilent(val) {
          const cb = this.onChange;
          this.onChange = null;
          this.select(val);
          this.onChange = cb;
        }
        firstValue() {
          const first = this.list.querySelector('.dd-item');
          return first ? first.dataset.value : null;
        }
        _esc(s) { const d = document.createElement('span'); d.textContent = s; return d.innerHTML; }
      }

      document.addEventListener('click', () => {
        document.querySelectorAll('.dd-menu:not(.hidden)').forEach(m => m.classList.add('hidden'));
        document.querySelectorAll('.dd').forEach(d => { if (d._dd) d._dd._open = false; });
      });

      /* ============ Independent Zoom ============ */
      function applyPdfZoom(pct) {
        state.pdfZoom = Math.max(PDF_ZOOM_MIN, Math.min(PDF_ZOOM_MAX, pct));
        document.documentElement.style.setProperty('--pdf-zoom', String(state.pdfZoom / 100));
        byId('pdf-zoom-label').textContent = state.pdfZoom + '%';
        const slider = byId('pdf-zoom-slider');
        slider.value = state.pdfZoom;
        slider.style.setProperty('--fill', ((state.pdfZoom - PDF_ZOOM_MIN) / (PDF_ZOOM_MAX - PDF_ZOOM_MIN) * 100) + '%');
        /* enable scroll only when zoomed past fit */
        const area = byId('pdf-scroll-area');
        if (area) area.classList.toggle('scrollable', state.pdfZoom > PDF_ZOOM_MIN);
      }

      function applyMdZoom(pct) {
        state.mdZoom = Math.max(MD_ZOOM_MIN, Math.min(MD_ZOOM_MAX, pct));
        document.documentElement.style.setProperty('--md-zoom', String(state.mdZoom / 100));
        byId('md-zoom-label').textContent = state.mdZoom + '%';
        const slider = byId('md-zoom-slider');
        slider.value = state.mdZoom;
        slider.style.setProperty('--fill', ((state.mdZoom - MD_ZOOM_MIN) / (MD_ZOOM_MAX - MD_ZOOM_MIN) * 100) + '%');
      }

      /* ============ Toast ============ */
      function showToast(message, type) {
        if (!message) return;
        const container = byId("toast-container");
        const el = document.createElement("div");
        const colorBorder = type === "error" ? "border-red-500/30" : type === "success" ? "border-green-500/30" : "border-g-border";
        const colorText = type === "error" ? "text-red-400" : type === "success" ? "text-green-400" : "text-g-dim";
        el.className = `bg-g-raised border ${colorBorder} rounded-lg px-3.5 py-2 text-[13px] ${colorText} shadow-lg pointer-events-auto max-w-[340px] toast-enter`;
        el.textContent = message;
        container.appendChild(el);
        setTimeout(() => { el.className = el.className.replace("toast-enter", "toast-leave"); setTimeout(() => el.remove(), 200); }, 2800);
      }

      function showTab(tabName) {
        document.querySelectorAll(".tab").forEach(btn => {
          const isActive = btn.dataset.tab === tabName;
          btn.classList.toggle("active", isActive);
          if (isActive) { btn.classList.add("bg-blue-500/10", "text-blue-400"); btn.classList.remove("text-g-dim"); }
          else { btn.classList.remove("bg-blue-500/10", "text-blue-400"); btn.classList.add("text-g-dim"); }
        });
        document.querySelectorAll(".section").forEach(el => el.classList.toggle("active", el.id === tabName));
      }
      document.querySelectorAll(".tab.active").forEach(btn => { btn.classList.add("bg-blue-500/10", "text-blue-400"); btn.classList.remove("text-g-dim"); });

      function setSpinner(id, visible) { const el = byId(id); if (el) el.classList.toggle("hidden", !visible); }

      async function fetchJSON(url, options) {
        const baseOptions = options || {};
        const method = String(baseOptions.method || "GET").toUpperCase();
        const queryJoin = url.includes("?") ? "&" : "?";
        const requestUrl = method === "GET" ? `${url}${queryJoin}_ts=${Date.now()}` : url;
        const response = await fetch(requestUrl, { cache: "no-store", ...baseOptions });
        if (!response.ok) {
          let detail = response.statusText;
          try { const p = await response.json(); detail = p.detail || JSON.stringify(p); } catch (err) {}
          throw new Error(detail);
        }
        return response.json();
      }

      function isTyping(t) { if (!t) return false; const tag = (t.tagName||"").toLowerCase(); return tag === "input" || tag === "textarea" || tag === "select" || t.isContentEditable; }"""


def init_js() -> str:
    """Return the init/bindEvents/keyboard JS that wires viewer + ELO together."""
    return """\
      /* ============ Events ============ */
      function bindEvents() {
        document.querySelectorAll(".tab").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
        document.querySelectorAll(".theme-btn").forEach(b => b.addEventListener("click", () => applyTheme(b.dataset.theme)));

        byId("viewer-prev").addEventListener("click", () => shiftViewerPage(-1));
        byId("viewer-next").addEventListener("click", () => shiftViewerPage(1));
        byId("viewer-page-go").addEventListener("click", () => gotoViewerPage(byId("viewer-page-jump").value));
        byId("viewer-page-jump").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); gotoViewerPage(e.target.value); } });
        byId("viewer-toggle-mode").addEventListener("click", () => { state.viewer.rendered = !state.viewer.rendered; loadViewerPage().catch(e => showToast(e.message, "error")); });

        /* PDF zoom controls */
        byId("pdf-zoom-out").addEventListener("click", () => applyPdfZoom(state.pdfZoom - PDF_ZOOM_STEP));
        byId("pdf-zoom-in").addEventListener("click", () => applyPdfZoom(state.pdfZoom + PDF_ZOOM_STEP));
        byId("pdf-zoom-slider").addEventListener("input", e => applyPdfZoom(Number(e.target.value)));

        /* MD zoom controls */
        byId("md-zoom-out").addEventListener("click", () => applyMdZoom(state.mdZoom - MD_ZOOM_STEP));
        byId("md-zoom-in").addEventListener("click", () => applyMdZoom(state.mdZoom + MD_ZOOM_STEP));
        byId("md-zoom-slider").addEventListener("input", e => applyMdZoom(Number(e.target.value)));

        document.addEventListener("keydown", (e) => {
          if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
          if (isTyping(e.target)) return;

          if (e.key === "Escape") {
            document.querySelectorAll('.dd-menu:not(.hidden)').forEach(m => m.classList.add('hidden'));
            document.querySelectorAll('.dd').forEach(d => { if (d._dd) d._dd._open = false; });
            return;
          }

          if (byId("viewer").classList.contains("active")) {
            const SCROLL_PX = 120;
            if (e.key === "ArrowLeft") { e.preventDefault(); shiftViewerPage(-1); }
            else if (e.key === "ArrowRight") { e.preventDefault(); shiftViewerPage(1); }
            /* W/S scroll the PDF panel */
            else if (e.key === "w" || e.key === "W") { e.preventDefault(); const el = byId('pdf-scroll-area'); if (el) el.scrollBy({ top: -SCROLL_PX, behavior: 'smooth' }); }
            else if (e.key === "s" || e.key === "S") { e.preventDefault(); const el = byId('pdf-scroll-area'); if (el) el.scrollBy({ top: SCROLL_PX, behavior: 'smooth' }); }
            else if (e.key === "a" || e.key === "A") { e.preventDefault(); const el = byId('pdf-scroll-area'); if (el) el.scrollBy({ left: -SCROLL_PX, behavior: 'smooth' }); }
            else if (e.key === "d" || e.key === "D") { e.preventDefault(); const el = byId('pdf-scroll-area'); if (el) el.scrollBy({ left: SCROLL_PX, behavior: 'smooth' }); }
            /* ArrowUp/ArrowDown scroll the markdown panel */
            else if (e.key === "ArrowUp") { e.preventDefault(); const el = byId('md-scroll-area'); if (el) el.scrollBy({ top: -SCROLL_PX, behavior: 'smooth' }); }
            else if (e.key === "ArrowDown") { e.preventDefault(); const el = byId('md-scroll-area'); if (el) el.scrollBy({ top: SCROLL_PX, behavior: 'smooth' }); }
            /* R toggles raw/rendered markdown */
            else if (e.key === "r" || e.key === "R") { e.preventDefault(); state.viewer.rendered = !state.viewer.rendered; loadViewerPage().catch(err => showToast(err.message, "error")); }
            /* Shift+minus/plus = MD zoom, plain minus/plus = PDF zoom */
            else if (e.key === "-") { e.preventDefault(); if (e.shiftKey) applyMdZoom(state.mdZoom - MD_ZOOM_STEP); else applyPdfZoom(state.pdfZoom - PDF_ZOOM_STEP); }
            else if (e.key === "=" || e.key === "+") { e.preventDefault(); if (e.shiftKey) applyMdZoom(state.mdZoom + MD_ZOOM_STEP); else applyPdfZoom(state.pdfZoom + PDF_ZOOM_STEP); }
            else if (e.key === "0") { e.preventDefault(); applyPdfZoom(100); applyMdZoom(100); }
          }

          if (byId("elo").classList.contains("active")) {
            /* B toggles arena/browse anywhere in ELO */
            if (e.key === "b" || e.key === "B") { e.preventDefault(); eloToggleMode(); }
            /* Browse mode: arrow keys navigate pages */
            else if (!state.elo.arenaMode && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
              e.preventDefault(); eloShiftPage(e.key === "ArrowLeft" ? -1 : 1);
            }
            /* Voting/actions require a pair */
            else if (state.elo.pair) {
              if (e.key === "1") { e.preventDefault(); submitEloVote("left_better"); }
              else if (e.key === "2") { e.preventDefault(); submitEloVote("right_better"); }
              else if (e.key === "3") { e.preventDefault(); submitEloVote("both_good"); }
              else if (e.key === "4") { e.preventDefault(); submitEloVote("both_bad"); }
              else if (e.key === "s" || e.key === "S") { e.preventDefault(); submitEloVote("skip"); }
              else if (e.key === "n" || e.key === "N") { e.preventDefault(); loadNextEloPair(); }
              else if (e.key === "r" || e.key === "R") { e.preventDefault(); state.elo.rendered = !state.elo.rendered; renderEloMarkdown(state.elo.pair); }
            }
          }
        });

        window.addEventListener("pageshow", () => scheduleViewerRefresh(50));
        window.addEventListener("focus", () => scheduleViewerRefresh(50));
        byId("viewer-image").addEventListener("error", () => showToast("PDF preview unavailable", "error"));

        byId("elo-next").addEventListener("click", () => loadNextEloPair());
        byId("elo-next-bottom").addEventListener("click", () => loadNextEloPair());
        byId("elo-toggle-mode").addEventListener("click", () => { state.elo.rendered = !state.elo.rendered; if (state.elo.pair) renderEloMarkdown(state.elo.pair); });
        byId("elo-mode-toggle").addEventListener("click", () => eloToggleMode());
        byId("elo-prev").addEventListener("click", () => eloShiftPage(-1));
        byId("elo-next-page").addEventListener("click", () => eloShiftPage(1));
        byId("elo-page-go").addEventListener("click", () => eloJumpToPage(byId("elo-page-jump").value));
        byId("elo-page-jump").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); eloJumpToPage(e.target.value); } });
        document.querySelectorAll("[data-vote]").forEach(b => b.addEventListener("click", () => submitEloVote(b.dataset.vote)));
        byId("elo-image").addEventListener("error", () => { if (state.elo.pair) eloSetColumns(2); });
        byId("elo-image").addEventListener("load", () => { if (state.elo.pair && state.elo._cols !== 3) eloSetColumns(3); });
      }

      async function init() {
        bindEvents();
        const saved = localStorage.getItem('tracr-theme') || 'dark';
        applyTheme(saved);
        /* init zoom sliders to default */
        applyPdfZoom(100);
        applyMdZoom(100);
        try { await refreshViewerData(); await loadEloJobs(); }
        catch (e) { showToast(e.message, "error"); }
      }
      init();"""
