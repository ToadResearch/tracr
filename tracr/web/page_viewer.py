"""Viewer section: HTML and JavaScript for the PDF/markdown viewer tab."""

from __future__ import annotations


def viewer_section_html() -> str:
    """Return the <section id='viewer'> HTML block."""
    return """\
      <!-- ==================== VIEWER ==================== -->
      <section id="viewer" class="section active">
        <!-- Toolbar -->
        <div class="flex items-end gap-2.5 mb-3 flex-wrap">
          <!-- Job dropdown -->
          <div class="flex flex-col gap-1 flex-1 min-w-[160px]">
            <label class="text-[10px] font-semibold text-g-muted uppercase tracking-widest">Job</label>
            <div class="dd relative" id="dd-viewer-job">
              <button type="button" class="dd-trigger flex items-center justify-between w-full h-[34px] rounded-lg border border-g-border bg-g-surface text-g-text text-[13px] font-sans px-2.5 cursor-pointer hover:border-g-hover focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-colors">
                <span class="dd-label truncate">Select...</span>
                <svg class="w-3.5 h-3.5 text-g-muted shrink-0 ml-2" fill="none" viewBox="0 0 20 20"><path stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="M6 8l4 4 4-4"/></svg>
              </button>
              <div class="dd-menu hidden absolute z-40 left-0 right-0 mt-1 rounded-lg border border-g-border bg-g-surface ring-1 ring-[var(--c-dd-ring)] dd-panel overflow-hidden">
                <div class="max-h-60 overflow-y-auto py-1"></div>
              </div>
            </div>
          </div>
          <!-- Output dropdown -->
          <div class="flex flex-col gap-1 flex-[1.6] min-w-[180px]">
            <label class="text-[10px] font-semibold text-g-muted uppercase tracking-widest">Output</label>
            <div class="dd relative" id="dd-viewer-output">
              <button type="button" class="dd-trigger flex items-center justify-between w-full h-[34px] rounded-lg border border-g-border bg-g-surface text-g-text text-[13px] font-sans px-2.5 cursor-pointer hover:border-g-hover focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-colors">
                <span class="dd-label truncate">Select...</span>
                <svg class="w-3.5 h-3.5 text-g-muted shrink-0 ml-2" fill="none" viewBox="0 0 20 20"><path stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="M6 8l4 4 4-4"/></svg>
              </button>
              <div class="dd-menu hidden absolute z-40 left-0 right-0 mt-1 rounded-lg border border-g-border bg-g-surface ring-1 ring-[var(--c-dd-ring)] dd-panel overflow-hidden">
                <div class="max-h-60 overflow-y-auto py-1"></div>
              </div>
            </div>
          </div>

          <!-- Page nav -->
          <div class="flex flex-col gap-1">
            <label class="text-[10px] font-semibold text-g-muted uppercase tracking-widest">Page</label>
            <div class="flex items-center gap-1">
              <button id="viewer-prev" class="h-[34px] w-[34px] rounded-lg border border-g-border bg-g-surface text-g-dim text-base flex items-center justify-center cursor-pointer hover:bg-g-panel hover:border-g-hover transition-all active:scale-95" title="Previous (Left arrow)">&larr;</button>
              <div class="dd relative" id="dd-viewer-page">
                <button type="button" class="dd-trigger flex items-center justify-between w-[100px] h-[34px] rounded-lg border border-g-border bg-g-surface text-g-text text-[13px] font-sans px-2.5 cursor-pointer hover:border-g-hover focus:outline-none focus:border-blue-500 transition-colors">
                  <span class="dd-label truncate">Page 1</span>
                  <svg class="w-3.5 h-3.5 text-g-muted shrink-0 ml-1" fill="none" viewBox="0 0 20 20"><path stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="M6 8l4 4 4-4"/></svg>
                </button>
                <div class="dd-menu hidden absolute z-40 left-0 mt-1 rounded-lg border border-g-border bg-g-surface ring-1 ring-[var(--c-dd-ring)] dd-panel overflow-hidden min-w-[100px]">
                  <div class="max-h-60 overflow-y-auto py-1"></div>
                </div>
              </div>
              <button id="viewer-next" class="h-[34px] w-[34px] rounded-lg border border-g-border bg-g-surface text-g-dim text-base flex items-center justify-center cursor-pointer hover:bg-g-panel hover:border-g-hover transition-all active:scale-95" title="Next (Right arrow)">&rarr;</button>
            </div>
          </div>

          <!-- Jump -->
          <div class="flex flex-col gap-1">
            <label class="text-[10px] font-semibold text-g-muted uppercase tracking-widest">Go to</label>
            <div class="flex gap-1">
              <input id="viewer-page-jump" type="number" min="1" step="1" placeholder="#" class="h-[34px] w-16 rounded-lg border border-g-border bg-g-surface text-g-text text-[13px] font-sans text-center focus:outline-none focus:border-blue-500 transition-colors appearance-none" />
              <button id="viewer-page-go" class="h-[34px] px-2.5 rounded-lg border border-g-border bg-g-surface text-g-text text-xs font-medium cursor-pointer hover:bg-g-panel hover:border-g-hover transition-all active:scale-95">Go</button>
            </div>
          </div>

          <!-- PDF Zoom -->
          <div class="flex flex-col gap-1">
            <label class="text-[10px] font-semibold text-g-muted uppercase tracking-widest">PDF Zoom</label>
            <div class="flex items-center gap-0">
              <button id="pdf-zoom-out" class="h-[34px] w-[34px] rounded-l-lg border border-g-border bg-g-surface text-g-dim text-sm font-bold flex items-center justify-center cursor-pointer hover:bg-g-panel hover:border-g-hover transition-all active:scale-95" title="Shrink PDF">&minus;</button>
              <div class="h-[34px] flex items-center border-y border-g-border bg-g-subtle px-2 gap-1.5">
                <input id="pdf-zoom-slider" type="range" min="100" max="400" step="10" value="100" class="zoom-slider w-16" />
                <span id="pdf-zoom-label" class="text-[11px] font-mono text-g-dim select-none tabular-nums min-w-[36px] text-center">100%</span>
              </div>
              <button id="pdf-zoom-in" class="h-[34px] w-[34px] rounded-r-lg border border-g-border bg-g-surface text-g-dim text-sm font-bold flex items-center justify-center cursor-pointer hover:bg-g-panel hover:border-g-hover transition-all active:scale-95" title="Expand PDF">+</button>
            </div>
          </div>

          <!-- MD Zoom -->
          <div class="flex flex-col gap-1">
            <label class="text-[10px] font-semibold text-g-muted uppercase tracking-widest">MD Zoom</label>
            <div class="flex items-center gap-0">
              <button id="md-zoom-out" class="h-[34px] w-[34px] rounded-l-lg border border-g-border bg-g-surface text-g-dim text-sm font-bold flex items-center justify-center cursor-pointer hover:bg-g-panel hover:border-g-hover transition-all active:scale-95" title="Shrink text">&minus;</button>
              <div class="h-[34px] flex items-center border-y border-g-border bg-g-subtle px-2 gap-1.5">
                <input id="md-zoom-slider" type="range" min="50" max="200" step="5" value="100" class="zoom-slider w-16" />
                <span id="md-zoom-label" class="text-[11px] font-mono text-g-dim select-none tabular-nums min-w-[36px] text-center">100%</span>
              </div>
              <button id="md-zoom-in" class="h-[34px] w-[34px] rounded-r-lg border border-g-border bg-g-surface text-g-dim text-sm font-bold flex items-center justify-center cursor-pointer hover:bg-g-panel hover:border-g-hover transition-all active:scale-95" title="Expand text">+</button>
            </div>
          </div>

          <!-- Mode -->
          <div class="flex flex-col gap-1">
            <label class="text-[10px] font-semibold text-g-muted uppercase tracking-widest">&nbsp;</label>
            <button id="viewer-toggle-mode" class="h-[34px] px-3 rounded-lg border border-g-border bg-g-surface text-g-text text-xs font-medium cursor-pointer hover:bg-g-panel hover:border-g-hover transition-all whitespace-nowrap">Rendered</button>
          </div>

          <!-- Spinner -->
          <div id="viewer-spinner" class="w-4 h-4 border-2 border-g-border border-t-blue-500 rounded-full hidden self-center mb-1 spin"></div>
        </div>

        <!-- Panels -->
        <div id="viewer-grid" class="viewer-grid grid grid-cols-2 gap-3">
          <!-- PDF Panel -->
          <div class="bg-g-surface border border-g-border rounded-xl flex flex-col overflow-hidden">
            <div class="flex items-center justify-between px-3.5 py-2.5 border-b border-g-border shrink-0">
              <span class="text-[11px] font-semibold text-g-muted uppercase tracking-wider">Source PDF</span>
              <span id="viewer-page-badge" class="text-[11px] text-g-muted bg-g-raised px-2 py-0.5 rounded-full tabular-nums">--</span>
            </div>
            <div id="pdf-scroll-area" class="pdf-scroll-area">
              <img id="viewer-image" class="rounded-lg shadow-lg block" alt="PDF page" />
            </div>
          </div>

          <!-- Markdown Panel -->
          <div class="bg-g-surface border border-g-border rounded-xl flex flex-col overflow-hidden md-panel">
            <div class="flex items-center justify-between px-3.5 py-2.5 border-b border-g-border shrink-0">
              <span class="text-[11px] font-semibold text-g-muted uppercase tracking-wider">Extracted Markdown</span>
              <span id="viewer-token-badge" class="text-[11px] text-g-muted bg-g-raised px-2 py-0.5 rounded-full tabular-nums">--</span>
            </div>
            <div id="md-scroll-area" class="flex-1 overflow-auto bg-g-subtle px-4 py-3.5">
              <div id="md-zoom-wrapper" class="md-zoom-wrapper">
                <pre id="viewer-md-raw" class="whitespace-pre-wrap break-words m-0 font-mono text-[12.5px] leading-relaxed text-g-dim"></pre>
                <div id="viewer-md-rendered" class="md-rendered"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Status bar -->
        <div class="flex items-center gap-4 pt-2 mt-2 flex-wrap text-[11px]">
          <div class="flex items-center gap-1.5 text-g-muted"><span>Model</span> <span class="text-g-dim tabular-nums" id="viewer-s-model">--</span></div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted"><span>Run</span> <span class="text-g-dim tabular-nums" id="viewer-s-run">--</span></div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted"><span>PDF</span> <span class="text-g-dim tabular-nums" id="viewer-s-pdf">--</span></div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted"><span>Tokens</span> <span class="text-g-dim tabular-nums" id="viewer-s-tokens">--</span></div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted"><span>Chars</span> <span class="text-g-dim tabular-nums" id="viewer-s-chars">--</span></div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted">
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">&larr;</kbd>
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">&rarr;</kbd>
            <span>navigate</span>
          </div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted">
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">W</kbd>
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">A</kbd>
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">S</kbd>
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">D</kbd>
            <span>scroll PDF</span>
          </div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted">
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">&uarr;</kbd>
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">&darr;</kbd>
            <span>scroll MD</span>
          </div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted">
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">-</kbd>
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">+</kbd>
            <span>PDF zoom</span>
          </div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted">
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">&#8679;-</kbd>
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">&#8679;+</kbd>
            <span>MD zoom</span>
          </div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted">
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">R</kbd>
            <span>raw/rendered</span>
          </div>
          <span class="w-1 h-1 rounded-full bg-g-border"></span>
          <div class="flex items-center gap-1.5 text-g-muted">
            <kbd class="inline-flex items-center h-[18px] px-1 text-[10px] font-sans text-g-muted bg-g-raised border border-g-border rounded font-medium">0</kbd>
            <span>reset zoom</span>
          </div>
        </div>
      </section>"""


def viewer_js() -> str:
    """Return viewer-specific JavaScript: dropdown init, data loading, page navigation."""
    return """\
      /* ============ Init Viewer Dropdowns ============ */
      const ddViewerJob = new Dropdown(byId('dd-viewer-job'), (val) => { state.viewer.jobId = val; loadViewerOutputs(); });
      byId('dd-viewer-job')._dd = ddViewerJob;

      const ddViewerOutput = new Dropdown(byId('dd-viewer-output'), (val) => { state.viewer.outputId = val; loadViewerPagesAndContent(); });
      byId('dd-viewer-output')._dd = ddViewerOutput;

      const ddViewerPage = new Dropdown(byId('dd-viewer-page'), (val) => { gotoViewerPage(val); });
      byId('dd-viewer-page')._dd = ddViewerPage;

      /* ============ Viewer Logic ============ */
      function selectedViewerOutput() {
        return state.viewer.outputs.find(item => item.output_id === state.viewer.outputId) || null;
      }
      function viewerPagesSorted() {
        const output = selectedViewerOutput();
        if (!output) return [];
        return (output.page_numbers || []).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
      }
      function updatePageBadge() {
        const pages = viewerPagesSorted();
        const idx = pages.indexOf(Number(state.viewer.pageNumber));
        byId("viewer-page-badge").textContent = pages.length ? `${idx + 1} / ${pages.length}` : "--";
      }

      async function loadViewerJobs() {
        const prev = state.viewer.jobId;
        setSpinner("viewer-spinner", true);
        try {
          const data = await fetchJSON("/api/web/jobs");
          state.viewer.jobs = data.jobs || [];
          if (!state.viewer.jobs.length) {
            ddViewerJob.setItems([], 'job_id', 'title');
            state.viewer.jobId = state.viewer.outputId = state.viewer.pageNumber = null;
            return;
          }
          ddViewerJob.setItems(state.viewer.jobs, 'job_id', 'title');
          const next = state.viewer.jobs.some(j => j.job_id === prev) ? prev : ddViewerJob.firstValue();
          ddViewerJob.selectSilent(next);
          state.viewer.jobId = next;
          await loadViewerOutputs();
        } finally { setSpinner("viewer-spinner", false); }
      }

      async function loadViewerOutputs() {
        if (!state.viewer.jobId) return;
        const prev = state.viewer.outputId;
        const data = await fetchJSON(`/api/web/jobs/${encodeURIComponent(state.viewer.jobId)}/outputs`);
        state.viewer.outputs = data.outputs || [];
        if (!state.viewer.outputs.length) {
          ddViewerOutput.setItems([], 'output_id', 'label');
          state.viewer.outputId = state.viewer.pageNumber = null;
          return;
        }
        ddViewerOutput.setItems(state.viewer.outputs, 'output_id', 'label');
        const next = state.viewer.outputs.some(o => o.output_id === prev) ? prev : ddViewerOutput.firstValue();
        ddViewerOutput.selectSilent(next);
        state.viewer.outputId = next;
        await loadViewerPagesAndContent();
      }

      async function loadViewerPagesAndContent() {
        if (!state.viewer.outputId) return;
        const pages = viewerPagesSorted();
        if (!pages.length) return;
        const pageItems = pages.map(p => ({ value: String(p), label: `Page ${p}` }));
        ddViewerPage.setItems(pageItems, 'value', 'label');
        const prev = Number(state.viewer.pageNumber);
        state.viewer.pageNumber = pages.includes(prev) ? prev : pages[0];
        ddViewerPage.selectSilent(String(state.viewer.pageNumber));
        byId("viewer-page-jump").value = String(state.viewer.pageNumber);
        await loadViewerPage();
      }

      function renderViewerMarkdown(payload) {
        const raw = byId("viewer-md-raw"), ren = byId("viewer-md-rendered");
        raw.textContent = payload.markdown_raw || "";
        ren.innerHTML = payload.markdown_html || "";
        if (state.viewer.rendered) { raw.style.display = "none"; ren.style.display = "block"; byId("viewer-toggle-mode").textContent = "Rendered"; }
        else { raw.style.display = "block"; ren.style.display = "none"; byId("viewer-toggle-mode").textContent = "Raw"; }
      }

      async function loadViewerPage() {
        if (!state.viewer.jobId || !state.viewer.outputId || !state.viewer.pageNumber) return;
        const url = `/api/web/jobs/${encodeURIComponent(state.viewer.jobId)}/viewer/page?output_id=${encodeURIComponent(state.viewer.outputId)}&page_number=${encodeURIComponent(state.viewer.pageNumber)}`;
        const data = await fetchJSON(url);
        state.viewer.pageNumber = Number(data.output.current_page);
        ddViewerPage.selectSilent(String(state.viewer.pageNumber));
        byId("viewer-page-jump").value = String(state.viewer.pageNumber);
        updatePageBadge();
        const img = byId("viewer-image");
        const join = data.image_url.includes("?") ? "&" : "?";
        img.src = `${data.image_url}${join}_ts=${Date.now()}`;
        renderViewerMarkdown(data);
        byId("viewer-s-model").textContent = data.output.model_label || "--";
        byId("viewer-s-run").textContent = data.output.run_number ?? "--";
        byId("viewer-s-pdf").textContent = data.output.pdf_label || "--";
        byId("viewer-s-tokens").textContent = data.output_tokens != null ? data.output_tokens.toLocaleString() : "--";
        byId("viewer-s-chars").textContent = data.output_characters != null ? data.output_characters.toLocaleString() : "--";
        byId("viewer-token-badge").textContent = data.output_tokens != null ? `${data.output_tokens.toLocaleString()} tok` : "--";
      }

      async function gotoViewerPage(pageNumber) {
        const pages = viewerPagesSorted();
        const target = Number(pageNumber);
        if (!pages.includes(target)) { showToast(`Page ${target} not available`, "error"); return; }
        state.viewer.pageNumber = target;
        await loadViewerPage();
      }

      async function shiftViewerPage(delta) {
        const pages = viewerPagesSorted();
        if (!pages.length) return;
        const idx = pages.indexOf(Number(state.viewer.pageNumber));
        if (idx < 0) return;
        const next = Math.max(0, Math.min(pages.length - 1, idx + delta));
        if (next === idx) return;
        state.viewer.pageNumber = pages[next];
        await loadViewerPage();
      }

      async function refreshViewerData() { await loadViewerJobs(); }

      function scheduleViewerRefresh(ms) {
        if (viewerRefreshTimer !== null) clearTimeout(viewerRefreshTimer);
        viewerRefreshTimer = setTimeout(() => { refreshViewerData().catch(e => showToast(e.message, "error")); viewerRefreshTimer = null; }, ms || 100);
      }"""
